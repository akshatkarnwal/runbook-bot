from pathlib import Path
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings as LlamaSettings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.config import settings

# configure llama index embeddings
def setup_llama_settings():
    LlamaSettings.embed_model = GeminiEmbedding(
        model_name=settings.embedding_model,
        api_key=settings.gemini_api_key
    )
    LlamaSettings.node_parser = SentenceSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )

def build_vector_store() -> PGVectorStore:
    return PGVectorStore.from_params(
        host=settings.db_host,
        port=int(settings.db_port),
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        table_name=settings.collection_name,
        embed_dim=3072,
    )

def ingest_documents() -> int:
    setup_llama_settings()
    data_path = Path(settings.data_dir)
    print(f"Loading documents from {data_path}/")
    reader = SimpleDirectoryReader(input_dir=str(data_path))
    documents = reader.load_data()
    print(f"Loaded {len(documents)} documents")

    vector_store = build_vector_store()
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True
    )
    print(f"Ingestion complete")
    return len(documents)

def get_retriever():
    setup_llama_settings()
    vector_store = build_vector_store()
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context
    )
    return index.as_retriever(similarity_top_k=settings.retrieval_k)

def build_llm():
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.gemini_api_key
    )

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an AI assistant for platform engineers at DNIF.
Answer questions using the context from runbooks and post-mortems below.
If the answer is not in the context, say so honestly.
Use conversation history to maintain context across messages.

Conversation history:
{history}

Relevant runbook context:
{context}"""),
    ("human", "{question}")
])

def query(question: str, history: str) -> str:
    retriever = get_retriever()
    llm = build_llm()

    # retrieve relevant chunks
    nodes = retriever.retrieve(question)
    context = "\n\n---\n\n".join(
        f"[{node.metadata.get('file_name', 'unknown')}]\n{node.text}"
        for node in nodes
    )

    chain = RAG_PROMPT | llm | StrOutputParser()
    return chain.invoke({
        "question": question,
        "history": history,
        "context": context
    })