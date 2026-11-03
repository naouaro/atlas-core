"""Quickstart — a tiny Arabic help-center mapped with zero cloud deps.

    python examples/quickstart.py

Runs fully offline (hashed local embeddings + NullLLM). For real quality install
a model:  pip install "atlas-core[local]"  (multilingual sentence-transformers),
or use the Bedrock/OpenAI providers.
"""
from atlas_core import Atlas
from atlas_core.ingest.documents import DocumentIngester
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM

DOCS = [
    {"id": "a1", "kind": "article", "title": "إصدار الشهادات للطلاب",
     "text": "كيفية منح شهادة إتمام الدورة للطالب وتخصيص قالب الشهادة."},
    {"id": "a2", "kind": "article", "title": "منح الشهادة يدوياً",
     "text": "خطوات منح شهادة يدوياً لطالب معيّن من لوحة التحكم."},
    {"id": "a3", "kind": "article", "title": "الربط مع بوابة دفع Stripe",
     "text": "إعداد بوابة الدفع Stripe لاستقبال المدفوعات من الطلاب."},
    {"id": "a4", "kind": "article", "title": "طرق استلام الإيرادات",
     "text": "كيف تستلم أرباحك والحسابات البنكية وطلبات السحب."},
    {"id": "a5", "kind": "article", "title": "إنشاء دورة جديدة",
     "text": "خطوات إنشاء دورة ورفع الدروس والفيديوهات وترتيب المحتوى."},
    {"id": "a6", "kind": "article", "title": "تسعير الدورات والكوبونات",
     "text": "ضبط أسعار الدورات وإنشاء أكواد خصم وكوبونات تسويقية."},
    {"id": "a7", "kind": "article", "title": "النشرة البريدية وأدوات التسويق",
     "text": "إرسال حملات بريدية للطلاب واستخدام أدوات التسويق لزيادة المبيعات."},
    {"id": "a8", "kind": "article", "title": "ربط النطاق المخصص (DNS)",
     "text": "توجيه نطاقك الخاص إلى منصة الأكاديمية عبر إعدادات DNS."},
]
LINKS = [{"src": "a2", "dst": "a1", "type": "related"}]

atlas = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
ing = DocumentIngester(DOCS, LINKS)
atlas.ingest(ing.nodes(), ing.links())
atlas.build()

print("\n== Narrative ==\n", atlas.narrative.text)
print("\n== Topics ==")
for t in atlas.topics():
    print(f"  [{t.id}] {t.label}  ({len(t.node_ids)} items)")
print("\n== Semantic search: 'كيف أعطي الطالب شهادة؟' ==")
for node, score in atlas.search("كيف أعطي الطالب شهادة؟", k=3):
    print(f"  {score:.3f}  {node.name}")
print("\n== Semantic search: 'استلام الأموال' ==")
for node, score in atlas.search("استلام الأموال", k=3):
    print(f"  {score:.3f}  {node.name}")
