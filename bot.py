import os
import asyncio
import requests
import feedparser
import re
from urllib.parse import quote

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- Проверка запроса ----------
def is_water_query(query):
    water_keywords = [
        "water",
        "membrane",
        "electrodialysis",
        "ion exchange",
        "bipolar",
        "dissociation",
        "recombination"
    ]
    
    query = query.lower()
    return any(k in query for k in water_keywords)


# ---------- Генерация ключевых слов ----------
def extract_keywords(texts):
    keywords = [
        "water dissociation",
        "water splitting",
        "recombination",
        "electrodialysis",
        "ion exchange membrane",
        "bipolar membrane",
        "electroconvection",
        "proton transport",
        "hydroxyl ions",
        "ion transport",
        "membrane processes"
    ]
    
    found = set()
    
    for text in texts:
        if not text:
            continue
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                found.add(kw)
    
    return list(found)


# ---------- Улучшение запроса ----------
def improve_query(user_query):
    return f"({user_query}) AND (water OR membrane OR electrodialysis OR ion exchange)"


# ---------- Проверка релевантности ----------
def is_relevant(text):
    if not text:
        return False
    
    text = text.lower()
    
    keywords = [
        "water",
        "membrane",
        "electrodialysis",
        "ion exchange",
        "bipolar",
        "dissociation",
        "recombination"
    ]
    
    score = sum(1 for k in keywords if k in text)
    
    return score >= 2


# ---------- Очистка HTML ----------
def clean_html(text):
    if not text:
        return ""
    return re.sub('<.*?>', '', text)


# ---------- Простое саммари ----------
def simple_summary(text):
    if not text:
        return "Нет аннотации"
    
    text = text.replace("\n", " ").strip()
    return text[:500] + "..."


# ---------- arXiv ----------
def search_arxiv(query):
    encoded_query = quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results=5"
    
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
        "rows": 5
    }
    
    r = requests.get(url, params=params)
    data = r.json()
    
    papers = []
    
    for item in data.get("message", {}).get("items", []):
        papers.append({
            "title": item.get("title", [""])[0],
            "abstract": clean_html(item.get("abstract", "")),
            "doi": item.get("DOI")
        })
    
    return papers


# ==============================
# ---------- TOOLS -------------
# ==============================

def tool_search_all(query):
    results = []
    texts = []
    
    # arXiv
    try:
        for p in search_arxiv(query):
            results.append({
                "title": p["title"],
                "text": p["summary"],
                "link": p["link"]
            })
            texts.append(p["summary"])
    except Exception as e:
        print("arXiv error:", e)
    
    # CrossRef
    try:
        for p in search_crossref(query):
            results.append({
                "title": p["title"],
                "text": p["abstract"],
                "link": f"https://doi.org/{p['doi']}" if p["doi"] else ""
            })
            texts.append(p["abstract"])
    except Exception as e:
        print("CrossRef error:", e)
    
    return results, texts


def tool_filter_relevant(papers):
    return [p for p in papers if is_relevant(p["text"] or p["title"])]


# ==============================
# ---------- TELEGRAM ----------
# ==============================

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "Привет! Я научный агент по электромембранным системам 🔬\n\n"
        "Работаю только с темами:\n"
        "- water dissociation\n"
        "- membranes\n"
        "- electrodialysis\n\n"
        "Напиши:\n/search ключевые слова"
    )


@dp.message(Command("search"))
async def search(msg: types.Message):
    user_query = msg.text.replace("/search", "").strip()
    
    if not user_query:
        await msg.answer("Напиши так:\n/search water dissociation membrane")
        return
    
    # ❗ Проверка тематики
    if not is_water_query(user_query):
        await msg.answer(
            "❌ Я работаю только с темами воды и мембран\n\n"
            "Попробуй:\n/search water dissociation membrane"
        )
        return
    
    await msg.answer("🔍 Ищу научные статьи...")
    
    query = improve_query(user_query)
    
    results, texts = tool_search_all(query)
    
    if not results:
        await msg.answer("Ничего не найдено 😢")
        return
    
    # ключевые слова
    keywords = extract_keywords(texts)
    
    if keywords:
        kw_text = "\n".join(f"- {k}" for k in keywords)
        await msg.answer(f"🧠 Рекомендуемые ключевые слова:\n{kw_text}")
    
    # фильтр
    filtered = tool_filter_relevant(results)
    
    if not filtered:
        await msg.answer("Не удалось найти релевантные статьи 😢")
        return
    
    # ответ
    for p in filtered[:5]:
        summary = simple_summary(p["text"])
        
        text = f"""
📄 {p['title']}

🔗 {p['link']}

📌 Аннотация:
{summary}
"""
        await msg.answer(text)


# ---------- запуск ----------

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())