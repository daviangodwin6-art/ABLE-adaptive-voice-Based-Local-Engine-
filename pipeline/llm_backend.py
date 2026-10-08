"""llama.cpp backend with the small part of GPT4All's interface that jarvis_v1 uses.

gpt4all 2.8.2 bundles an old llama.cpp that cannot load newer architectures (Gemma 3), so those models
go through llama-cpp-python instead. CPU only (n_gpu_layers=0).
"""
from pathlib import Path


class LlamaCppLLM:
    def __init__(self, model_name, model_path, n_threads, n_batch=8, n_ctx=1024, **_):
        from llama_cpp import Llama
        self.gemma = "gemma" in model_name.lower()
        self.llm = Llama(str(Path(model_path) / model_name), n_ctx=n_ctx, n_threads=n_threads, n_batch=n_batch,
                         n_gpu_layers=0, verbose=False)

    def generate(self, prompt, max_tokens=200, n_batch=None, streaming=False, callback=None):
        """Like GPT4All.generate: a string, or a token generator when streaming. n_batch is fixed at load time.
        callback(token_index, token_text) returning False stops the reply (the live demo uses it)."""
        if self.gemma:  # Gemma's own turn format; llama.cpp adds <bos> itself
            prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"

        def tokens():
            for i, chunk in enumerate(self.llm.create_completion(prompt, max_tokens=max_tokens, stream=True,
                                                                 stop=["<end_of_turn>"])):
                text = chunk["choices"][0]["text"]
                if callback and not callback(i, text):
                    return
                yield text

        return tokens() if streaming else "".join(tokens())


def demo():
    """Self-check: fake llama object, no model file needed."""
    llm = LlamaCppLLM.__new__(LlamaCppLLM)
    llm.gemma = True
    seen = []

    class Fake:
        def create_completion(self, prompt, **k):
            seen.append(prompt)
            return ({"choices": [{"text": t}]} for t in ["Paris", ".", " User:"])
    llm.llm = Fake()
    assert llm.generate("hi") == "Paris. User:"
    assert seen[0].startswith("<start_of_turn>user\nhi<end_of_turn>")
    assert list(llm.generate("hi", streaming=True, callback=lambda i, t: "User" not in t)) == ["Paris", "."]
    print("llm_backend ok")


if __name__ == "__main__":
    demo()
