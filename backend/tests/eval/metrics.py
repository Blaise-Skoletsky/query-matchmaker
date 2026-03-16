"""Evaluation metrics for LLM output quality."""


def rouge_l_score(hypothesis: str, reference: str) -> float:
    """Compute ROUGE-L F-measure between hypothesis and reference."""
    from rouge_score import rouge_scorer
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    return scorer.score(reference, hypothesis)["rougeL"].fmeasure


def bleu_score(hypothesis: str, reference: str) -> float:
    """Compute BLEU score between hypothesis and reference."""
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    smoothing = SmoothingFunction().method1
    return sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothing)


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between sentence embeddings."""
    from sentence_transformers import SentenceTransformer, util
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return float(util.cos_sim(model.encode(text_a), model.encode(text_b))[0][0])


def precision_recall_f1(predictions: list[str], labels: list[str]) -> dict:
    """Compute element-wise precision, recall, F1."""
    tp = sum(1 for p, l in zip(predictions, labels) if p == l)
    p = tp / len(predictions) if predictions else 0
    r = tp / len(labels) if labels else 0
    f1 = 2 * p * r / (p + r) if (p + r) else 0
    return {"precision": p, "recall": r, "f1": f1}
