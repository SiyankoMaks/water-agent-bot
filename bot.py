import os
import asyncio
import requests
import feedparser
from urllib.parse import quote

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

# --- ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_KEY)


# ---------- Улучшение запроса ----------
def improve_query(user_query):
    return f"({user_query}) AND (membrane OR electrodialysis OR ion exchange) AND (water dissociation OR recombination)"


# ---------- arXiv ----------
def search_arxiv(query):
    encoded_query = quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results=3"
    
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
    
    for item in data.get("message", {}).get("items", []):
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
            {
                "role": "user",
                "content": f"""
Сделай краткий научный разбор статьи:
- суть работы
- есть ли диссоциация воды
- теория или эксперимент
- ключевой результат

И переведи на русский:

{text}
"""
            }
        ]
    )
    
    return response.choices[0].message.content


# ---------- Telegram ----------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "Привет! Я научный агент 🔬\n\n"
        "Напиши:\n/search ключевые слова\n\n"
        "Пример:\n/search water dissociation electrodialysis"
    )


@dp.message(Command("search"))
async def search(msg: types.Message):
    user_query = msg.text.replace("/search", "").strip()
    
    if not user_query:
        await msg.answer("Напиши так:\n/search water dissociation membrane")
        return
    
    await msg.answer("🔍 Ищу научные статьи...")
    
    # улучшение запроса
    query = improve_query(user_query)
    
    results = []
    
    # --- arXiv ---
    try:
        arxiv_papers = search_arxiv(query)
        for p in arxiv_papers:
            results.append({
                "title": p["title"],
                "text": p["summary"],
                "link": p["link"]
            })
    except Exception as e:
        print("arXiv error:", e)
    
    # --- CrossRef ---
    try:
        cross_papers = search_crossref(query)
        for p in cross_papers:
            results.append({
                "title": p["title"],
                "text": p["abstract"],
                "link": f"https://doi.org/{p['doi']}" if p["doi"] else ""
            })
    except Exception as e:
        print("CrossRef error:", e)
    
    if not results:
        await msg.answer("Ничего не найдено 😢")
        return
    
    # --- Ответ ---
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