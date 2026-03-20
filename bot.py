import os
import asyncio
import requests
import feedparser

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_KEY)

# ---------- arXiv ----------
def search_arxiv(query):
    url = f"http://export.arxiv.org/api/query?search_query=all:{query}&max_results=3"
    feed = feedparser.parse(url)
    
    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title,
            "summary": entry.summary,
            "link": entry.link
        })
    
    return papers


# ---------- CrossRef ----------
def search_crossref(query):
    url = "https://api.crossref.org/works"
    
    params = {
        "query": query,
        "rows": 3
    }
    
    r = requests.get(url, params=params)
    data = r.json()
    
    papers = []
    
    for item in data["message"]["items"]:
        papers.append({
            "title": item.get("title", [""])[0],
            "doi": item.get("DOI"),
            "abstract": item.get("abstract", "")
        })
    
    return papers


# ---------- GPT ----------
def summarize(text):
    if not text:
        return "Нет аннотации"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"""
Сделай краткий научный разбор:
- суть работы
- есть ли диссоциация воды
- теория или эксперимент
- ключевой результат

И переведи на русский:

{text}
"""}
        ]
    )
    
    return response.choices[0].message.content


# ---------- Telegram ----------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Привет! Напиши:\n/search ключевые слова")


@dp.message(Command("search"))
async def search(msg: types.Message):
    query = msg.text.replace("/search", "").strip()
    
    if not query:
        await msg.answer("Напиши так:\n/search water dissociation membrane")
        return
    
    await msg.answer("🔍 Ищу статьи...")
    
    results = []
    
    # arXiv
    arxiv_papers = search_arxiv(query)
    for p in arxiv_papers:
        results.append({
            "title": p["title"],
            "text": p["summary"],
            "link": p["link"]
        })
    
    # CrossRef
    cross_papers = search_crossref(query)
    for p in cross_papers:
        results.append({
            "title": p["title"],
            "text": p["abstract"],
            "link": f"https://doi.org/{p['doi']}" if p["doi"] else ""
        })
    
    # Ответ
    for p in results[:5]:
        summary = summarize(p["text"])
        
        text = f"""
📄 {p['title']}

🔗 {p['link']}

🧠 {summary}
"""
        await msg.answer(text)


# ---------- запуск ----------

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())