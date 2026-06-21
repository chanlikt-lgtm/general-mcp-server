"""ML/AI utility tools — pure Python + scikit-learn + standard lib.
   No large model downloads required; uses TF-IDF and rule-based approaches
   so they work fully offline without GPU.
"""
import math
import re
from mcp.server.fastmcp import FastMCP


def register_ml_utils_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def tokenize_text(text: str, lowercase: bool = True, remove_stopwords: bool = False) -> str:
        """
        Tokenize text into individual words/tokens.
        text: input string to tokenize.
        lowercase: convert all tokens to lowercase (default true).
        remove_stopwords: remove common English stop words like 'the', 'is', 'a' (default false).
        Returns token count, unique count, and the full token list.
        """
        STOPWORDS = {
            "a","an","the","is","are","was","were","be","been","being",
            "have","has","had","do","does","did","will","would","could","should",
            "may","might","shall","can","need","dare","ought","used","to","of",
            "in","for","on","with","at","by","from","as","into","through",
            "during","before","after","above","below","between","out","off",
            "over","under","again","further","then","once","and","but","or",
            "nor","so","yet","both","either","neither","not","only","own",
            "same","than","too","very","just","that","this","these","those",
            "i","me","my","we","our","you","your","he","him","his","she",
            "her","it","its","they","them","their","what","which","who","whom",
        }
        tokens = re.findall(r"[a-zA-Z0-9']+", text)
        if lowercase:
            tokens = [t.lower() for t in tokens]
        if remove_stopwords:
            tokens = [t for t in tokens if t.lower() not in STOPWORDS]
        unique = sorted(set(tokens))
        preview = tokens[:50]
        return (
            f"Total tokens  : {len(tokens)}\n"
            f"Unique tokens : {len(unique)}\n"
            f"Tokens (first 50): {preview}\n"
            f"Unique (sorted): {unique[:30]}{'...' if len(unique)>30 else ''}"
        )

    @mcp.tool()
    def embedding_similarity(text1: str, text2: str) -> str:
        """
        Compute cosine similarity between two texts using TF-IDF vectors.
        text1, text2: any two strings to compare.
        Returns a similarity score from 0.0 (unrelated) to 1.0 (identical),
        plus the top shared terms driving the similarity.
        No model download required — uses scikit-learn TF-IDF.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            docs = [text1, text2]
            vec  = TfidfVectorizer(stop_words="english").fit_transform(docs)
            sim  = float(cosine_similarity(vec[0], vec[1])[0][0])
            # find shared terms
            feat = TfidfVectorizer(stop_words="english").fit(docs).get_feature_names_out()
            arr  = vec.toarray()
            shared = [f for f in feat if arr[0][list(feat).index(f)] > 0 and arr[1][list(feat).index(f)] > 0][:10]
            label = "very similar" if sim > 0.8 else "somewhat similar" if sim > 0.4 else "dissimilar"
            return (
                f"Similarity  : {sim:.4f} ({label})\n"
                f"Shared terms: {shared}"
            )
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def summarize_text(text: str, sentences: int = 3) -> str:
        """
        Extractive text summarization — selects the N most important sentences.
        text: the text to summarize (works best with 5+ sentences).
        sentences: number of sentences to include in summary (default 3).
        Returns the extracted summary sentences plus a word-count comparison.
        No model download required — uses TF-IDF sentence scoring.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np
            # Split into sentences
            sent_list = re.split(r'(?<=[.!?])\s+', text.strip())
            sent_list = [s.strip() for s in sent_list if len(s.split()) >= 3]
            if not sent_list:
                return "Error: text too short to summarize (need at least 3 sentences)."
            n = min(sentences, len(sent_list))
            if len(sent_list) == 1:
                return sent_list[0]
            tfidf = TfidfVectorizer(stop_words="english")
            mat   = tfidf.fit_transform(sent_list).toarray()
            scores = mat.sum(axis=1)          # sentence importance = sum of TF-IDF weights
            top_idx = sorted(np.argsort(scores)[-n:])   # keep original order
            summary = " ".join(sent_list[i] for i in top_idx)
            orig_words = len(text.split())
            summ_words = len(summary.split())
            return (
                f"Summary ({summ_words} words, {int(summ_words/orig_words*100)}% of original):\n\n"
                f"{summary}"
            )
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def classify_sentiment(text: str) -> str:
        """
        Classify the sentiment of a text as Positive, Negative, or Neutral.
        text: any English text — review, comment, feedback, etc.
        Returns sentiment label, confidence score, and key signal words found.
        Uses a rule-based lexicon approach — no model download required.
        """
        POSITIVE = {
            "good","great","excellent","amazing","wonderful","fantastic","love",
            "happy","pleased","satisfied","perfect","best","awesome","brilliant",
            "outstanding","superb","helpful","recommend","enjoy","beautiful",
            "nice","pleasant","positive","delightful","impressive","easy",
            "efficient","fast","clear","useful","reliable","fun","clean",
            "smooth","intuitive","affordable","worth","exceptional","incredible",
        }
        NEGATIVE = {
            "bad","terrible","awful","horrible","poor","worst","hate","angry",
            "disappointed","frustrated","broken","useless","waste","slow",
            "difficult","complicated","confusing","expensive","overpriced",
            "unreliable","buggy","annoying","disappointing","fails","error",
            "problem","issue","wrong","ugly","boring","painful","mediocre",
            "inadequate","lacking","inferior","defective","misleading",
        }
        INTENSIFIERS = {"very","really","extremely","absolutely","completely","totally","so"}
        NEGATORS = {"not","no","never","isn't","wasn't","doesn't","don't","didn't","can't","won't"}

        tokens = re.findall(r"[a-z']+", text.lower())
        pos_hits, neg_hits = [], []
        score = 0.0
        for i, tok in enumerate(tokens):
            prev = tokens[i-1] if i > 0 else ""
            mult = 1.5 if prev in INTENSIFIERS else 1.0
            if prev in NEGATORS:
                mult = -1.0
            if tok in POSITIVE:
                score += 1.0 * mult
                pos_hits.append(tok)
            elif tok in NEGATIVE:
                score -= 1.0 * mult
                neg_hits.append(tok)

        total = max(len(tokens), 1)
        norm  = score / (total ** 0.5)
        if norm > 0.3:
            label, conf = "Positive", min(0.99, 0.5 + norm * 0.3)
        elif norm < -0.3:
            label, conf = "Negative", min(0.99, 0.5 + abs(norm) * 0.3)
        else:
            label, conf = "Neutral", 0.5 + abs(norm) * 0.1

        return (
            f"Sentiment   : {label}\n"
            f"Confidence  : {conf:.2f}\n"
            f"Pos signals : {list(set(pos_hits))[:8]}\n"
            f"Neg signals : {list(set(neg_hits))[:8]}\n"
            f"Raw score   : {score:.2f}"
        )

    @mcp.tool()
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> str:
        """
        Split a long text into overlapping chunks suitable for RAG/embedding pipelines.
        text: the full text to split.
        chunk_size: max words per chunk (default 500).
        overlap: number of words to repeat at the start of the next chunk (default 50).
        Returns each chunk numbered with its word range, separated by '---'.
        Use to prepare documents for vector database ingestion.
        """
        words = text.split()
        if not words:
            return "Error: empty text."
        chunk_size = max(10, int(chunk_size))
        overlap    = max(0, min(int(overlap), chunk_size - 1))
        chunks = []
        start  = 0
        idx    = 1
        while start < len(words):
            end   = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(f"[Chunk {idx} | words {start+1}–{end}]\n{chunk}")
            idx  += 1
            start = end - overlap
            if end == len(words):
                break
        total_words = len(words)
        return (
            f"Total words: {total_words} | Chunks: {len(chunks)} | "
            f"Size: {chunk_size}w | Overlap: {overlap}w\n\n"
            + "\n\n---\n\n".join(chunks)
        )
