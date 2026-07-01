# 📦 Gestão de Suprimentos

> Transformando processos de suprimentos em um fluxo digital integrado, rastreável e inteligente.

[![Deploy](https://img.shields.io/badge/Deploy-Render-46E3B7?style=flat-square&logo=render)](https://suprimentos.onrender.com)
[![Stack](https://img.shields.io/badge/Stack-Python%20%7C%20FastAPI%20%7C%20PostgreSQL-0D47A1?style=flat-square&logo=python)](#stack)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## 🎯 Sobre o Projeto

**Gestão de Suprimentos** é uma plataforma desenvolvida para conectar solicitações, aprovações, compras e entregas em uma única solução integrada. Elimina processos manuais, garante rastreabilidade completa e utiliza IA para validação inteligente de cadastros.

### ✨ Diferenciais

- 🔄 **Fluxo End-to-End** - Desde solicitação até entrega
- 🤖 **IA Aplicada** - Validação inteligente com Gemini, Llama e Mistral
- 📊 **KPIs em Tempo Real** - Dashboards operacionais e técnicos
- 🔐 **Segurança Enterprise** - RBAC, JWT, OAuth2
- ☁️ **Cloud Ready** - Escalável e pronto para produção
- 📈 **Business Intelligence** - Análise de custos e economia

---

## 🏗️ Stack Tecnológico

### Backend
```
Python 3.9+
├── FastAPI + Uvicorn
├── SQLAlchemy (ORM)
├── Pydantic (validação)
├── python-jose + passlib (autenticação)
└── HTTPX (requisições async)
```

### Frontend
```
Vanilla JavaScript + HTML5
├── Tailwind CSS (estilização)
├── Chart.js (gráficos)
├── ECharts (dashboards)
└── Responsive Design
```

### Data & Storage
```
PostgreSQL / SQLite
├── Supabase (cloud)
├── Migrations automáticas
└── Supabase Storage (anexos)
```

### IA & ML
```
Gemini 2.0 Flash
Groq Llama 3.3
Cerebras Llama 3.3
Mistral Small
OpenRouter (agregador)
Sentence Transformers
```

---

## 🚀 Como Rodar Localmente

### Pré-requisitos
- Python 3.9+
- pip ou conda
- Um banco PostgreSQL/SQLite

### 1. Clone o Repositório
```bash
git clone https://github.com/psgeisa/suprimentos.git
cd suprimentos
```

### 2. Configure o Ambiente
```bash
# Crie um virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt
```

### 3. Configure as Variáveis de Ambiente
```bash
# Copie o exemplo e edite
cp .env.example .env

# Edite .env com suas credenciais:
# DATABASE_URL=postgresql://user:pass@localhost/suprimentos
# JWT_SECRET_KEY=sua_chave_segura
# GEMINI_API_KEY=sua_chave_gemini
# etc.
```

### 4. Execute o Servidor
```bash
# Terminal 1: Backend
python run.py
# ou
uvicorn app.main:app --reload

# Terminal 2 (opcional): Popule o banco com dados de teste
python teste/seed_supabase.py
python teste/seed_plataforma.py
```

### 5. Acesse a Aplicação
```
Frontend: http://localhost:8000
API Docs: http://localhost:8000/docs
```

---

## 📊 KPIs Disponíveis

### KPIs de Negócio
Acesse em: `/api/kpis-negocio`

| Métrica | Descrição |
|---------|-----------|
| 📋 Abertas | Solicitações em aberto |
| ⏳ Em Andamento | Processando compra |
| ✅ Concluídas | Finalizadas no período |
| 📈 Taxa de Conclusão | % de fechamento |
| ⏱️ Tempo Médio | Dias solicitação → entrega |
| 💰 Valor Comprado | Total gasto |
| 🎯 Economia | Diferença orçado vs. pago |
| 🚨 Críticas | Pedidos urgentes pendentes |

**+ Sparklines, Funil, Rankings, Categorias, Estabelecimentos...**

### KPIs de Plataforma
Acesse em: `/api/kpis-plataforma`

| Área | Métricas |
|------|----------|
| 🧠 **Qualidade de Dados** | Taxa de aceitação IA, duplicidades evitadas, campos problemáticos |
| 🔒 **Segurança** | Total de acessos, rotas mais usadas, auditoria |
| 📱 **Utilização** | Usuários ativos, heatmaps de acesso, funcionalidades |
| 🔄 **Fluxo** | Funil de usuário, progressão de status |

---

## 🗂️ Estrutura do Projeto

```
suprimentos/
├── app/
│   ├── main.py                 # Inicialização FastAPI
│   ├── auth.py                 # Autenticação JWT/OAuth2
│   ├── database.py             # Configuração DB
│   ├── models/                 # SQLAlchemy Models
│   │   ├── suprimento.py
│   │   ├── user.py
│   │   ├── compra_log.py
│   │   ├── item.py
│   │   └── ...
│   └── routers/                # API Endpoints
│       ├── suprimentos.py      # CRUD suprimentos
│       ├── aprovacoes.py       # Fluxo de aprovação
│       ├── compras.py          # Processamento compras
│       ├── kpis_negocio.py     # KPIs operacionais
│       ├── kpis_plataforma.py  # KPIs técnicos
│       └── ...
├── frontend/
│   └── static/
│       ├── index.html          # SPA única
│       └── vendor/             # Libs (Chart.js, ECharts)
├── teste/
│   ├── seed_supabase.py        # Dados de teste
│   └── seed_plataforma.py      # KPI samples
├── requirements.txt
├── run.py
└── render.yaml                 # Config deploy
```

---

## 🔐 Autenticação & Permissões

### Papéis (RBAC)
```
├── Admin          → Acesso total
├── Comprador      → Processamento de compras
├── Aprovador      → Aprovação de solicitações
├── Solicitante    → Criação de pedidos
└── Viewer         → Consulta apenas
```

### Fluxo de Login
```
POST /api/auth/login
├── Validar credenciais
├── Gerar JWT
└── Retornar token
```

---

## 🤖 IA & Validação Inteligente

### Pipeline Híbrido
```
Entrada do Usuário
    ↓
Regras de Negócio (rápido)
    ↓
Modelo de IA (preciso)
    ↓
Sugestão Inteligente
    ↓
Aprovação/Rejeição do Usuário
    ↓
Log & Aprendizado
```

### Modelos Suportados
- **Gemini 2.0 Flash** - Latência ultra-baixa
- **Groq Llama 3.3** - Velocidade
- **Cerebras Llama 3.3** - Inferência rápida
- **Mistral Small** - Eficiência

---

## 📈 Fluxo Principal

```
┌─────────────────────────────────────────┐
│  1. SOLICITAÇÃO (Pendente)              │
│     Usuário cria pedido de suprimento   │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  2. APROVAÇÃO (Aprovado)                │
│     Aprovador valida e autoriza         │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  3. COMPRA (Em Andamento)               │
│     Comprador processa & emite OC       │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  4. ENTREGA (Entregue)                  │
│     Material recebido & validado        │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  5. CONCLUSÃO (Concluído)               │
│     Processo finalizado, análise pronta │
└─────────────────────────────────────────┘
```

---

## 🛠️ Desenvolvimento

### Rodar Testes
```bash
# Ainda não há testes? Comece aqui:
pytest tests/ -v
```

### Documentação Automática
```
http://localhost:8000/docs     # Swagger UI
http://localhost:8000/redoc    # ReDoc
```

### Criar Migrações (Alembic)
```bash
alembic revision --autogenerate -m "descrição"
alembic upgrade head
```

---

## 🌐 Deploy

### Render
A aplicação está configurada para deploy automático no Render:

```yaml
# render.yaml
services:
  - type: web
    name: suprimentos
    runtime: python-3.11
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Deploy:**
```bash
git push  # Render faz deploy automático
```

---

## 📝 Variáveis de Ambiente

```bash
# Database
DATABASE_URL=postgresql://user:pass@host/db

# JWT & Segurança
JWT_SECRET_KEY=sua_chave_muito_segura_aqui
JWT_ALGORITHM=HS256

# IA APIs
GEMINI_API_KEY=sua_chave
GROQ_API_KEY=sua_chave
MISTRAL_API_KEY=sua_chave
OPENROUTER_API_KEY=sua_chave

# Supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_anon_key

# App
ENVIRONMENT=production
DEBUG=False
```

---

## 🔗 Links Importantes

| Link | Descrição |
|------|-----------|
| 🔗 [Aplicação](https://suprimentos.onrender.com) | Deploy em produção |
| 📚 [API Docs](https://suprimentos.onrender.com/docs) | Swagger interativo |
| 👤 [LinkedIn](https://www.linkedin.com/in/geisa-reis/) | Sobre a desenvolvedora |
| 🎯 [Portfólio](https://portfolio-gamma-two-j3ogrq9zaj.vercel.app/) | Outros projetos |
| 💻 [GitHub](https://github.com/psgeisa) | Código aberto |

---

## 📄 Licença

Este projeto está sob licença MIT. Veja [LICENSE](LICENSE) para mais detalhes.

---

## 🤝 Contribuições

Sugestões e melhorias são bem-vindas! Abra uma issue ou PR.

---

<div align="center">

**Desenvolvido com ❤️ por [Geisa Reis](https://github.com/psgeisa)**

⭐ Se gostou, dê uma estrela! ⭐

</div>
