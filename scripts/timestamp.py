"""Timestamp a file with OpenTimestamps, as `ots stamp` does, using only the core library.

    python scripts/timestamp.py forward/SHA256SUMS                 # writes forward/SHA256SUMS.ots
    python scripts/timestamp.py --upgrade forward/SHA256SUMS.ots   # adds the Bitcoin attestation

The OpenTimestamps command-line client needs python-bitcoinlib, which cannot
load on Windows without OpenSSL's old DLLs; stamping does not need it. Only
the file's SHA-256 digest, behind a random nonce, is sent to the public
calendars; they put it into the Bitcoin blockchain within hours. Anyone can
then check the proof with the standard client: `ots upgrade` and then
`ots verify <file>.ots` (https://opentimestamps.org).
"""

from __future__ import annotations

import os
import sys

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.serialize import StreamSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile

CALENDARS = ["https://a.pool.opentimestamps.org", "https://b.pool.opentimestamps.org",
             "https://a.pool.eternitywall.com"]


def stamp(path: str) -> list[str]:
    with open(path, "rb") as f:
        detached = DetachedTimestampFile.from_fd(OpSHA256(), f)
    tip = detached.timestamp.ops.add(OpAppend(os.urandom(16))).ops.add(OpSHA256())
    reached = []
    for url in CALENDARS:
        try:
            tip.merge(RemoteCalendar(url).submit(tip.msg, timeout=20))
            reached.append(url)
        except Exception as e:      # one calendar down is fine; the proof needs only one
            print(f"{url}: {type(e).__name__}: {e}")
    if not reached:
        raise SystemExit("no calendar reached; nothing written")
    with open(path + ".ots", "wb") as fd:
        detached.serialize(StreamSerializationContext(fd))
    return reached


def upgrade(ots_path: str) -> int:
    """Ask each calendar for the Bitcoin attestation of a pending proof, as `ots upgrade` does.

    Returns how many Bitcoin attestations the proof holds afterwards; the file
    is rewritten only if that number grew.
    """
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
    from opentimestamps.core.serialize import StreamDeserializationContext

    with open(ots_path, "rb") as f:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))

    def bitcoin() -> int:
        return sum(isinstance(a, BitcoinBlockHeaderAttestation) for _, a in detached.timestamp.all_attestations())

    before = bitcoin()

    def walk(ts) -> None:
        for att in list(ts.attestations):
            if isinstance(att, PendingAttestation):
                try:
                    ts.merge(RemoteCalendar(att.uri).get_timestamp(ts.msg, timeout=20))
                except Exception as e:      # not confirmed yet, or the calendar is down: try again later
                    print(f"{att.uri}: not yet ({type(e).__name__})")
        for sub in ts.ops.values():
            walk(sub)

    walk(detached.timestamp)
    after = bitcoin()
    if after > before:
        with open(ots_path, "wb") as fd:
            detached.serialize(StreamSerializationContext(fd))
    return after


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--upgrade":
        print(f"{upgrade(sys.argv[2])} Bitcoin attestation(s) in {sys.argv[2]}")
    else:
        for url in stamp(sys.argv[1]):
            print(f"submitted to {url}")
        print(f"wrote {sys.argv[1]}.ots")
