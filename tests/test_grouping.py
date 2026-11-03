from atlas_core import Atlas, Node
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM


def _atlas():
    a = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    nodes = []
    for i in range(6):
        nodes.append(Node(id=f"A{i}", kind="course", name=f"دورة تسويق {i}",
                          text="تسويق رقمي وإعلانات", group="academy:A"))
    for i in range(6):
        nodes.append(Node(id=f"B{i}", kind="course", name=f"دورة برمجة {i}",
                          text="برمجة وتطوير ويب", group="academy:B"))
    a.ingest(nodes)
    a.embed_all()
    return a


def test_search_scopes_to_group():
    a = _atlas()
    a_hits = a.search("تسويق", k=20, group="academy:A")
    assert a_hits and all(n.group == "academy:A" for n, _ in a_hits)
    glob = a.search("تسويق", k=20)
    assert {n.group for n, _ in glob} == {"academy:A", "academy:B"}  # global sees both


def test_group_vs_global_topics_are_separate():
    a = _atlas()
    a.cluster()                       # global topics (group=None)
    a.cluster(group="academy:A")      # academy A topics
    assert all(t.group is None for t in a.topics())            # global
    at = a.topics(group="academy:A")
    assert at and all(t.group == "academy:A" for t in at)
    # an academy's topics only cover its own nodes
    ids = {nid for t in at for nid in t.node_ids}
    assert ids and all(i.startswith("A") for i in ids)


def test_all_nodes_group_filter():
    a = _atlas()
    assert len(a.store.all_nodes(group="academy:A")) == 6
    assert len(a.store.all_nodes()) == 12


def test_groups_listing():
    a = _atlas()
    assert a.groups() == ["academy:A", "academy:B"]
