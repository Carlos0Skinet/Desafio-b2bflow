CREATE TABLE tabela_contatos (
  id SERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  numero TEXT NOT NULL,
  Status TEXT,
  uuid UUID DEFAULT gen_random_uuid(),
  updated_at TIMESTAMP DEFAULT NOW()
);