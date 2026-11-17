
import os
import numpy as np
import pandas as pd
import streamlit as st
import snowflake.connector
from google import genai
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = "gemini-embedding-001"
CHAT_MODEL = "openai/gpt-oss-20b"

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

groq_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
NEW_REVIEWS = 500
TOP_K = 5
CACHE_FILE = "review_embeddings.parquet"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def read_reviews_from_snowflake():
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )

    query = f"""
        SELECT REVIEW_ID, CITY, RATING, COMMENT
        FROM DINESTREAM.STAGING.STG_REVIEWS
        SAMPLE ({NEW_REVIEWS} ROWS)
    """

    df = conn.cursor().execute(query).fetch_pandas_all()
    conn.close()

    df.columns = [col.lower() for col in df.columns]
    return df


def embed(texts):
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts
    )

    return [item.values for item in response.embeddings]


@st.cache_data()
def load_reviews():
    if os.path.exists(CACHE_FILE):
        return pd.read_parquet(CACHE_FILE)

    df = read_reviews_from_snowflake()
    df["embedding"] = embed(df["comment"].tolist())
    df.to_parquet(CACHE_FILE)

    return df


st.title("Chat with your Dinestream Reviews")
st.caption(f"Searching {NEW_REVIEWS} review, answering with {CHAT_MODEL} model")


def ask_llm(question, top_reviews):
    context = ""

    for _, row in top_reviews.iterrows():
        context += f" ({row['city']}, {row['rating']} stars) {row['comment']}\n"

    system_prompt = (
        "Answer ONLY using the customer reviews provided. "
        "Be concise. If the reviews don't covert it, say so"
    )

    user_prompt = f"Questions: {question}\n\nReviews:\n{context}"

    response = groq_client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    return response.choices[0].message.content


def find_similar_reviews(question, review_df):
    question_embedding = np.array(embed([question])[0])

    review_embeddings = np.array(
        review_df["embedding"].tolist()
    )

    similarities = (
        review_embeddings @ question_embedding
    ) / (
        np.linalg.norm(review_embeddings, axis=1)
        * np.linalg.norm(question_embedding)
    )

    top_indices = np.argsort(similarities)[::-1][:TOP_K]

    return review_df.iloc[top_indices]


review_df = load_reviews()

question = st.text_input(
    "Ask a question about your reviews:",
    placeholder="e.g. What are the most common complaints about delivery?",
)

if question:
    top_reviews = find_similar_reviews(question, review_df)
    answer = ask_llm(question, top_reviews)

    st.markdown("**Answer:**")
    st.write(answer)

    with st.expander("Reviews used to build this answer"):
        st.dataframe(
            top_reviews[["city", "rating", "comment"]],
            hide_index=True
        )
