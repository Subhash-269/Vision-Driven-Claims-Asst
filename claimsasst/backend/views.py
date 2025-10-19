from django.http import JsonResponse

def test(request):
	"""Simple test endpoint to verify routing and server health.

	Returns a small JSON payload with status and message.
	"""
	data = {
		"status": "ok",
		"message": "Backend test endpoint is reachable",
	}
	return JsonResponse(data)
