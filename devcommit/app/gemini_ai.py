#!/usr/bin/env python
"""Generate a git commit message using AI"""

import os
import re
import sys
import warnings

# Suppress warnings from AI libraries
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '3'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

warnings.filterwarnings('ignore', message='.*ALTS.*')
warnings.filterwarnings('ignore', category=UserWarning)

from devcommit.utils.logger import Logger, config
from devcommit.utils.git import KnownError
from .ai_providers import get_ai_provider
from .prompt import generate_prompt

logger_instance = Logger("__ai__")
logger = logger_instance.get_logger()


def normalize_commit_response(response: str) -> str:
    """Normalize AI response to ensure proper formatting of commit messages"""
    result = response.strip()
    
    # Remove markdown code fences that some models add
    result = re.sub(r'^```[\w]*\n?', '', result)  # Remove opening ```
    result = re.sub(r'\n?```$', '', result)        # Remove closing ```
    result = result.strip()
    
    # If no pipe separator but has newlines, convert newlines to pipes
    if "|" not in result and "\n" in result:
        messages = []
        for line in result.split("\n"):
            line = line.strip()
            if line:
                # Skip markdown code fences
                if line.startswith('```') or line == '```':
                    continue
                # Remove common numbering patterns: "1. ", "1) ", "- ", etc.
                line = re.sub(r'^\d+[\.\)]\s*', '', line)  # Remove "1. " or "1) "
                line = re.sub(r'^[-*•]\s*', '', line)      # Remove "- " or "* " or "• "
                if line:
                    messages.append(line)
        result = "|".join(messages)
    
    return result


def generateCommitMessage(diff: str) -> str:
    """Return a generated commit message using configured AI provider"""
    # Suppress stderr to hide warnings during API calls
    _stderr = sys.stderr
    _devnull_out = open(os.devnull, 'w')
    
    try:
        # Load Configuration Values
        max_no = config("MAX_NO", default=1, cast=int)
        locale = config("LOCALE", default="en-US")
        commit_type = config("COMMIT_TYPE", default="normal")
        max_tokens = config("MAX_TOKENS", default=8192, cast=int)
        
        # Generate prompt
        prompt_text = generate_prompt(max_tokens, max_no, locale, commit_type)
        
        # Get AI provider based on configuration
        sys.stderr = _devnull_out
        provider = get_ai_provider(config)
        sys.stderr = _stderr
        
        # Generate commit message
        sys.stderr = _devnull_out
        response = provider.generate_commit_message(diff, prompt_text, max_tokens)
        sys.stderr = _stderr
        
        # Normalize response to handle different formatting from various providers
        normalized_response = normalize_commit_response(response)
        
        return normalized_response

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error generating commit message: {error_msg}")
        
        # Raise KnownError with user-friendly message that includes error details
        # This prevents error messages from being shown as commit options
        # while still informing the user what went wrong
        raise KnownError(
            f"Failed to generate commit message: {error_msg}. "
            f"Please check your API configuration and try again."
        )
    finally:
        # Restore stderr and close devnull
        sys.stderr = _stderr
        _devnull_out.close()
