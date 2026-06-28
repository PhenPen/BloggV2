from fastapi import FastAPI
from fastapi.responses import HTMLResponse


from posts import posts as pst


app = FastAPI()


@app.get('/',response_class=HTMLResponse, include_in_schema=False)
@app.get('/posts',response_class=HTMLResponse, include_in_schema=False)
def posts_page():
    return f'<H1>{pst[0]['title']}</H1><br><H1>{pst[1]['title']}</H1>'


@app.get("/api/posts")
def posts():
    return {'posts' : pst}





