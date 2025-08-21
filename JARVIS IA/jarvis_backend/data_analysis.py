# data_analysis.py
import io
import numpy as np
import pandas as pd
import plotly.express as px
from contextlib import redirect_stdout
from config import openai_client

def executar_analise_profunda(df):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        print("--- RESUMO ESTATÍSTICO (NUMÉRICO) ---\n")
        print(df.describe(include=np.number))
        print("\n\n--- RESUMO CATEGÓRICO ---\n")
        if not df.select_dtypes(include=['object', 'category']).empty:
            print(df.describe(include=['object', 'category']))
        else:
            print("Nenhuma coluna de texto (categórica) encontrada.")
        # ... (resto da sua lógica de análise profunda) ...
    return buffer.getvalue()

def analisar_dados_com_ia(prompt_usuario, df):
    schema = df.head().to_string()
    prompt_gerador_codigo = f"""
    Você é um gerador de código Python para análise de dados com Pandas.
    O usuário tem um dataframe `df` com o seguinte schema:
    {schema}
    A pergunta do usuário é: "{prompt_usuario}"
    Sua tarefa é gerar um código Python, e SOMENTE o código, para obter os dados necessários.
    - Use `print()` para exibir resultados brutos.
    - Se pedir um gráfico, use `plotly.express` e atribua a figura a `fig`.
    - Use `numeric_only=True` em agregações.
    """
    try:
        # ... (sua lógica para gerar e executar o código Python) ...
        # IMPORTANTE: A parte que gera um gráfico (`return {"type": "plot", "content": fig}`)
        # precisará ser adaptada. A API deve retornar o JSON do gráfico (fig.to_json())
        # e o frontend será responsável por renderizá-lo com Plotly.js.
        codigo_gerado = "..." # Lógica de chamada da OpenAI
        local_vars = {"df": df, "pd": pd, "px": px}
        exec(codigo_gerado, local_vars)

        if "fig" in local_vars:
            # Retorna a especificação do gráfico em JSON
            return {"type": "plot", "content": local_vars["fig"].to_json()}

        # ... (resto da lógica de interpretação) ...
        resumo_claro = "..." # Lógica de chamada da OpenAI
        return {"type": "text", "content": resumo_claro}
    except Exception as e:
        # ... (sua lógica de tratamento de erro) ...
        return {"type": "text", "content": f"Erro na análise: {e}"}