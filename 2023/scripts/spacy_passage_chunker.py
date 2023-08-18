from typing import List

import spacy


class SpacyPassageChunker:

    def __init__(self, max_len: int, stride: int, model: str = 'en_core_web_sm'):
        self.max_len = max_len
        self.stride = stride
        self.document_sentences = []
        try:
            self.model = spacy.load(model,
                                    exclude=["parser", "tagger", "ner", "attribute_ruler", "lemmatizer", "tok2vec"])
        except OSError:
            print(f"Downloading spaCy model {model}")
            spacy.cli.download(model)
            print("Finished downloading model")
            self.model = spacy.load(model,
                                    exclude=["parser", "tagger", "ner", "attribute_ruler", "lemmatizer", "tok2vec"])
        self.model.enable_pipe("senter")
        self.model.max_length = 1500000000  # for documents that are longer than the spacy character limit

    @staticmethod
    def download_spacy_model(model="en_core_web_sm"):
        print(f"Downloading spaCy model {model}")
        spacy.cli.download(model)
        print("Finished downloading model")

    @staticmethod
    def load_model(model="en_core_web_sm"):
        return spacy.load(model, exclude=["parser", "tagger", "ner", "attribute_ruler", "lemmatizer", "tok2vec"])

    def tokenize_document(self, document_body: str) -> None:
        document_body = document_body.strip()
        spacy_document = self.model(document_body[:10000])
        self.document_sentences = list(spacy_document.sents)

    def chunk_document(self) -> List[str]:
        sentences = self.document_sentences
        segments = []

        for i in range(0, len(sentences), self.stride):
            segment = ' '.join([str(s) for s in sentences[i:i + self.max_len]])
            segments.append(segment)
            if i + self.max_len >= len(sentences):
                break
        return segments
