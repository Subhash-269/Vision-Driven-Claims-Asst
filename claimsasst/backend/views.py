from django.http import JsonResponse
from PyPDF2 import PdfReader
import os

def test(request):
	"""Simple test endpoint to verify routing and server health.

	Returns a small JSON payload with status and message.
	"""
	data = {
		"status": "ok",
		"message": "Backend test endpoint is reachable",
        
	}
	return JsonResponse(data)

def text_extract(request):
	"""Simple test endpoint to verify routing and server health.

	Returns a small JSON payload with status and message.
	"""
	data = {
		"status": "ok",
		"message": "Backend test endpoint is reachable",
	}
	
    
	return JsonResponse(data)


def indexfinder(request):
	"""Simple test endpoint to verify routing and server health.

	Returns a small JSON payload with status and message.
	"""
	data = {
		"status": "ok",
		"message": "Backend test endpoint is reachable",
	}
	return JsonResponse(data)


