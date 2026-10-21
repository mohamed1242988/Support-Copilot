def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
	if chunk_size <= 0:
		raise ValueError("chunk_size must be positive")
	if overlap < 0 or overlap >= chunk_size:
		raise ValueError("overlap must be non-negative and smaller than chunk_size")

	text = text.strip()
	if not text:
		return []

	chunks = []
	start = 0
	while start < len(text):
		end = min(start + chunk_size, len(text))
		if end < len(text):
			boundary = text.rfind(" ", start, end)
			if boundary > start:
				end = boundary

		chunk = text[start:end].strip()
		if chunk:
			chunks.append(chunk)
		if end == len(text):
			break

		start = max(end - overlap, start + 1)
		while start < len(text) and text[start].isspace():
			start += 1

	return chunks
