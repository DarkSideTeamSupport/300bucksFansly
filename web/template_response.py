from __future__ import annotations

import inspect
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates


def render_template(
	templates: Jinja2Templates,
	request: Request,
	name: str,
	context: dict[str, Any] | None = None,
):
	"""TemplateResponse: Starlette 1.x (request, name, ctx) и 0.41 (name, {request, …})."""
	ctx = dict(context or {})
	params = list(inspect.signature(templates.TemplateResponse).parameters)
	if params and params[0] == "request":
		return templates.TemplateResponse(request, name, ctx)
	ctx["request"] = request
	return templates.TemplateResponse(name, ctx)
