"""
Memory-to-EMO Translator Projector

This module provides the dual-write translator that converts legacy memory.*
events to new emo.* events while maintaining backward compatibility.
"""

from .translator_memory_to_emo import MemoryToEMOTranslator

__all__ = ["MemoryToEMOTranslator"]
