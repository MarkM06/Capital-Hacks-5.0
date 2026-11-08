"""
CLIP road-condition classifier. OWNER: Alex.

Uses OpenAI CLIP (openai/clip-vit-base-patch32, MIT license) through Hugging Face.
No training: CLIP compares the image to the text prompts below and picks the best match.

Test on its own:
    python clip_model.py Images
"""
import sys
from pathlib import Path

from PIL import Image

CLIP_MODEL = "openai/clip-vit-base-patch32"   # downloads ~600 MB on first run

# Several phrasings per label make CLIP more reliable. Edit the wording, keep the label names.
PROMPTS = {
    "dry road": [
        "a traffic camera photo of a dry highway with bare pavement in daylight",
        "a highway at night with no snow visible on the driving lanes",
    ],
    "wet road": [
        "a nighttime traffic camera on a cleared highway, bare wet lanes with vehicle headlights, snow only at road edges",
        "a traffic camera showing a highway where the lanes are almost completely bare with minimal snow remaining",
    ],
    "slush / partly covered": [
        "a traffic camera showing a highway with significant snow covering most of the travel lanes",
        "a highway with snow and slush visible across the road surface with tire tracks through it",
    ],
    "snow-covered": [
        "a traffic camera photo of a highway completely covered in deep snow with no visible pavement",
        "a road buried in snow with all lanes fully covered and no tire tracks visible",
    ],
    "fog / low visibility": [
        "a traffic camera photo of a highway in thick fog",
        "a highway with very low visibility due to fog or mist",
    ],
    "camera obstructed": [
        "a blurry traffic camera image with a dirty or blocked lens",
        "a camera lens covered with snow or water drops",
    ],
}
SNOW_LABELS = ("slush / partly covered", "snow-covered")


class ClipClassifier:
    """classify(image) -> (label, confidence 0-1, snow_score 0-1, all_scores dict)"""

    def __init__(self):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        print(f"Loading {CLIP_MODEL} (first run downloads ~600 MB)...")
        self.model = CLIPModel.from_pretrained(CLIP_MODEL).eval()
        self.processor = CLIPProcessor.from_pretrained(CLIP_MODEL)
        self.labels = list(PROMPTS)
        self.texts = [p for label in self.labels for p in PROMPTS[label]]
        self.owner = [label for label in self.labels for _ in PROMPTS[label]]

    def classify(self, image: Image.Image):
        inputs = self.processor(text=self.texts, images=image, return_tensors="pt", padding=True)
        with self.torch.no_grad():
            probs = self.model(**inputs).logits_per_image.softmax(dim=1)[0].tolist()
        scores = {label: 0.0 for label in self.labels}
        for label, p in zip(self.owner, probs):
            scores[label] += p
        best = max(scores, key=scores.get)
        snow_score = sum(scores[l] for l in SNOW_LABELS)
        return best, round(scores[best], 3), round(snow_score, 3), {k: round(v, 3) for k, v in scores.items()}


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "Images")
    clf = ClipClassifier()
    for path in sorted(folder.glob("*")):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            label, conf, snow, _ = clf.classify(Image.open(path).convert("RGB"))
            print(f"{path.name[-30:]:30s}  {label:24s} {conf:.0%}   snow score {snow:.2f}")
