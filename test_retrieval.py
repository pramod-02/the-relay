from app.retrieval import Passage, retrieve

def test_retrieve_matches_relevant_terms():
    passages = [
        Passage("attention_v7.pdf", 2, "The Transformer uses attention mechanisms to process sequence representations."),
        Passage("moshi_v1.pdf", 4, "Moshi is a speech-text foundation model for dialogue.")
    ]
    found = retrieve("Transformer attention", passages, k=1)
    assert found
    assert found[0].paper == "attention_v7.pdf"
