"""Loaders that turn raw logs into normalised :class:`EventRecord` streams.

Supported inputs
----------------
* generic CSV with a column mapping (Zeek conn.log exports, CIC-IDS flows, ...)
* LANL "Comprehensive, Multi-Source Cyber-Security Events" auth.txt / flows.txt / redteam.txt
  (https://csr.lanl.gov/data/cyber1/) -- the files are large, so all loaders stream and accept
  ``max_rows`` / time bounds.
"""

from __future__ import annotations

import csv
import gzip
from datetime import datetime, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

from src.core.models import EventRecord

PORT_TYPES = {
    88: "kerberos_tgs", 53: "dns", 389: "ldap", 636: "ldap", 445: "smb_file", 139: "smb_file",
    3389: "auth_remote", 5985: "auth_remote", 5986: "auth_remote", 22: "auth_remote",
    80: "http", 443: "http", 8080: "http",
}
UPLOAD_BYTES = 5_000_000


def _open(path: str):
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path, "r", newline="")


def _ts(seconds: float) -> datetime:
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc)


def normalize_event_type(protocol: Optional[str], dst_port: Optional[int], nbytes: Optional[int]) -> str:
    """Map a flow to the RefineMatch event vocabulary using its service port and volume."""
    etype = PORT_TYPES.get(dst_port or -1, "conn")
    if etype == "http" and nbytes is not None and nbytes >= UPLOAD_BYTES:
        return "http_upload"
    return etype


def load_csv(path: str, mapping: Dict[str, str], time_format: Optional[str] = None,
             max_rows: Optional[int] = None) -> List[EventRecord]:
    """Load a generic CSV. ``mapping`` maps EventRecord fields to CSV column names.

    Required keys: timestamp, source, destination. If ``event_type`` is not mapped it is derived
    from protocol / destination_port / bytes.
    """
    out: List[EventRecord] = []
    with _open(path) as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            if max_rows is not None and i >= max_rows:
                break
            raw_t = row[mapping["timestamp"]]
            if time_format:
                t = datetime.strptime(raw_t, time_format).replace(tzinfo=timezone.utc)
            else:
                try:
                    t = _ts(float(raw_t))
                except ValueError:
                    t = datetime.fromisoformat(raw_t)
                    if t.tzinfo is None:
                        t = t.replace(tzinfo=timezone.utc)

            def get(k, cast=str):
                col = mapping.get(k)
                if not col or row.get(col) in (None, "", "-"):
                    return None
                try:
                    return cast(row[col])
                except ValueError:
                    return None

            dport = get("destination_port", lambda x: int(float(x)))
            nbytes = get("bytes", lambda x: int(float(x)))
            proto = get("protocol")
            etype = get("event_type") or normalize_event_type(proto, dport, nbytes)
            out.append(EventRecord(
                timestamp=t, source=row[mapping["source"]], destination=row[mapping["destination"]],
                event_type=etype, protocol=proto, source_port=get("source_port", lambda x: int(float(x))),
                destination_port=dport, bytes=nbytes, duration=get("duration", float), label=get("label"),
            ))
    out.sort(key=lambda e: e.ts)
    return out


# --------------------------------------------------------------------------- LANL

def _lanl_rows(path: str, start: Optional[int], end: Optional[int], max_rows: Optional[int]) -> Iterator[List[str]]:
    with _open(path) as fh:
        for i, line in enumerate(fh):
            if max_rows is not None and i >= max_rows:
                break
            parts = line.rstrip("\n").split(",")
            t = int(parts[0])
            if start is not None and t < start:
                continue
            if end is not None and t >= end:
                break  # LANL files are time-sorted
            yield parts


def load_lanl_auth(path: str, start: Optional[int] = None, end: Optional[int] = None,
                   max_rows: Optional[int] = None, redteam: Optional[Set[Tuple[int, str, str]]] = None
                   ) -> List[EventRecord]:
    """auth.txt: time,src_user@domain,dst_user@domain,src_computer,dst_computer,
    auth_type,logon_type,auth_orientation,success/failure

    Computer-to-computer events only (self-authentications are dropped)."""
    out = []
    for p in _lanl_rows(path, start, end, max_rows):
        if len(p) < 9:
            continue
        t, _su, _du, sc, dc, atype, ltype, orient, ok = p[:9]
        if sc == dc or sc == "?" or dc == "?" or ok != "Success":
            continue
        if atype == "Kerberos" and orient == "TGS":
            etype = "kerberos_tgs"
        elif atype == "Kerberos" and orient == "TGT":
            etype = "kerberos_tgt"
        elif ltype in ("Network", "RemoteInteractive", "NewCredentials") and orient == "LogOn":
            etype = "auth_remote"
        else:
            continue
        label = None
        if redteam is not None and (int(t), sc, dc) in redteam:
            label = "attack:lateral_movement"
        out.append(EventRecord(timestamp=_ts(int(t)), source=sc, destination=dc, event_type=etype,
                               protocol=atype, label=label))
    return out


def load_lanl_flows(path: str, start: Optional[int] = None, end: Optional[int] = None,
                    max_rows: Optional[int] = None) -> List[EventRecord]:
    """flows.txt: time,duration,src_computer,src_port,dst_computer,dst_port,protocol,packet_count,byte_count"""
    out = []
    for p in _lanl_rows(path, start, end, max_rows):
        if len(p) < 9:
            continue
        t, dur, sc, sp, dc, dp, proto, _pk, nb = p[:9]
        try:
            dport = int(dp.lstrip("N")) if dp.lstrip("N").isdigit() else None
        except ValueError:
            dport = None
        nbytes = int(nb)
        out.append(EventRecord(timestamp=_ts(int(t)), source=sc, destination=dc,
                               event_type=normalize_event_type(proto, dport, nbytes), protocol=proto,
                               destination_port=dport, bytes=nbytes, duration=float(dur)))
    return out


def load_lanl_redteam(path: str) -> Set[Tuple[int, str, str]]:
    """redteam.txt: time,user@domain,src_computer,dst_computer"""
    rt = set()
    with _open(path) as fh:
        for line in fh:
            p = line.strip().split(",")
            if len(p) >= 4:
                rt.add((int(p[0]), p[2], p[3]))
    return rt


def merge_streams(*streams: Iterable[EventRecord]) -> List[EventRecord]:
    merged = [e for s in streams for e in s]
    merged.sort(key=lambda e: e.ts)
    return merged
