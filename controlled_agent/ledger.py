"""Append-only hash-chained audit events; partial/corrupt journal fails closed."""
import json
import os
from .manifests import encoded, object_hash
from .path_guard import no_links
from .redaction import clean


class Ledger:
    def __init__(self, directory):
        self.path = no_links(directory / "events.jsonl")

    def events(self):
        no_links(self.path)
        if not self.path.exists():
            return []
        previous = "0" * 64
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            body = {k: v for k, v in record.items() if k != "hash"}
            if record["previous"] != previous or object_hash(body) != record["hash"]:
                raise ValueError("ledger chain corrupted")
            previous = record["hash"]
            records.append(record)
        return records

    def append(self, event):
        records = self.events()
        body = {"previous": records[-1]["hash"] if records else "0" * 64, "sequence": len(records), "event": clean(event)}
        record = {**body, "hash": object_hash(body)}
        no_links(self.path)
        with self.path.open("ab") as stream:
            stream.write(encoded(record) + b"\n"); stream.flush(); os.fsync(stream.fileno())
