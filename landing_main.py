import uvicorn


if __name__ == "__main__":
	uvicorn.run("landing.app:app", host="127.0.0.1", port=8090, reload=False)
