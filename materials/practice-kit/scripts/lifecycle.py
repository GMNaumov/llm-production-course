"""Применение актуального журнала удаления/отзыва поверх старой копии."""

from common import ROOT, WORK, read_json, write_json
from rag import authorized, bm25

original = read_json(ROOT / "data/corpus.json")
write_json(WORK / "corpus-backup.json", original)
ledger = {
    "tombstones": ["release"],
    "revoked": ["shortage"],
    "policy_version": "training-A-v2",
}
write_json(WORK / "rights-current.json", ledger)
restored = read_json(WORK / "corpus-backup.json")
effective = authorized(restored, "A", ledger["tombstones"], ledger["revoked"])
write_json(WORK / "corpus-restored.json", effective)
report = {
    "backup_rows": len(restored),
    "effective_ids": [d["id"] for d in effective],
    "release_search_after_restore": bm25("выпуск спецификации", effective),
    "removed_document_present": any(d["document"] == "release" for d in effective),
    "revoked_document_present": any(d["document"] == "shortage" for d in effective),
    "note": "В этом эталоне нет кэша/истории. При их добавлении применять ту же текущую политику и инвалидировать результаты.",
}
write_json(WORK / "lifecycle.json", report)
print(report)
