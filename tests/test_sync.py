from atlas_core import Atlas, Node
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM


class CountingEmbedder(LocalEmbeddingProvider):
    calls = 0
    def embed(self, texts):
        CountingEmbedder.calls += len(texts)
        return super().embed(texts)


def _n(i, text, group="g"):
    return Node(id=f"n{i}", kind="course", name=f"course {i}", text=text, group=group)


def test_sync_reembeds_only_changed():
    CountingEmbedder.calls = 0
    a = Atlas(embedder=CountingEmbedder(), llm=NullLLM())
    a.sync([_n(1, "alpha"), _n(2, "beta"), _n(3, "gamma")])
    assert CountingEmbedder.calls == 3          # first time: all embedded
    # re-sync: one changed (n2), one new (n4), two unchanged (n1,n3)
    CountingEmbedder.calls = 0
    r = a.sync([_n(1, "alpha"), _n(2, "beta CHANGED"), _n(3, "gamma"), _n(4, "delta")])
    assert CountingEmbedder.calls == 2          # only changed + new re-embedded
    assert r["reembedded"] == 2 and r["reused"] == 2
    assert len(a.store.all_nodes()) == 4


def test_sync_prunes_deleted_in_group():
    a = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    a.sync([_n(1, "a"), _n(2, "b"), _n(3, "c")], prune_group="g")
    # next sync drops n3 → should be pruned
    r = a.sync([_n(1, "a"), _n(2, "b")], prune_group="g")
    assert r["pruned"] == 1
    assert {n.id for n in a.store.all_nodes()} == {"n1", "n2"}


def test_sync_prune_is_group_scoped():
    a = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    a.sync([_n(1, "a", "A"), _n(2, "b", "B")])
    # prune only group A with n1 still present → B untouched
    a.sync([_n(1, "a", "A")], prune_group="A")
    assert {n.id for n in a.store.all_nodes()} == {"n1", "n2"}
