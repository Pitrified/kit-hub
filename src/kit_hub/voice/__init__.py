"""Voice note session management.

This package handles live cooking dictation sessions: audio clips are
uploaded, transcribed via Whisper, and accumulated as a ``RecipeNote``.
The frozen session can then be converted to a structured ``RecipeCore``
via ``VoiceToRecipeConverter``.
"""
