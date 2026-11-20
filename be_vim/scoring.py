"""Local neural image/text similarity. No fake score or fallback evaluator."""

import torch
from PIL import Image, ImageDraw, ImageFont
from transformers import AutoModel, AutoProcessor

from .editor import COLORS, H, W
from .slides import DRAWING_PROMPT

MODEL = "google/siglip2-base-patch16-224"


class Judge:
    def __init__(self, font):
        self.font = ImageFont.truetype(font, 20)
        self.processor = AutoProcessor.from_pretrained(MODEL, use_fast=False)
        self.model = AutoModel.from_pretrained(MODEL).eval()
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.model.to(self.device)

    def render(self, snap):
        im = Image.new("RGB", (W * 12, H * 24), "black")
        d = ImageDraw.Draw(im)
        for y, line in enumerate(snap["lines"]):
            for x, c in enumerate(line):
                if c == "█":
                    d.rectangle((x*12, y*24, x*12+11, y*24+23), fill=COLORS[snap["colors"][y][x]])
                    continue
                d.text(
                    (x * 12, y * 24),
                    c,
                    font=self.font,
                    fill=COLORS[snap["colors"][y][x]],
                )
        return im

    def score(self, snapshots, keyword):
        if not snapshots:
            return []
        images = [self.render(s) for s in snapshots]
        inputs = self.processor(
            text=["An ASCII portrait of a person." if keyword == DRAWING_PROMPT else f"An ASCII drawing of a {keyword}."],
            images=images,
            return_tensors="pt",
            padding="max_length",
            max_length=64,
        ).to(self.device)
        with torch.inference_mode():
            out = self.model(**inputs)
        # Explicit similarity index, not a calibrated probability.
        return out.logits_per_image[:, 0].cpu().tolist()
