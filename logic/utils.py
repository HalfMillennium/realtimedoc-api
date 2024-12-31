import torch
from transformers import AutoTokenizer, AutoModel

CHROMA_PATH = "chroma"
CONSUMER_SPENDING_DATA = "../data/spending/us_consumers_october"
NATIONAL_SPENDING_DATA = "../data/spending/us_national_november"

# Load HuggingFace model and tokenizer
model_name = "sentence-transformers/all-MiniLM-L6-v2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

def embed_text(text: str) -> torch.Tensor:
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().tolist()