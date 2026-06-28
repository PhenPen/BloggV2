from fastapi import FastAPI
from posts import posts as pst
from fastapi.responses import HTMLResponse



app = FastAPI()

@app.get("/posts", response_class=HTMLResponse, include_in_schema=False)
@app.get("/home", response_class=HTMLResponse, include_in_schema=False)
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def homepage():
    return f'<H1>{pst[0]['title']}</H1><H3>{pst[0]['content']}</H3><br><H1>{pst[1]['title']}</H1><H3>{pst[1]['content']}</H3>'

@app.get("/api/posts")
def home():
    return {'posts' : pst}

