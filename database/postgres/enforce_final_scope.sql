-- Escopo obrigatório do banco final:
--   * comentários: somente português brasileiro (código canônico pt-BR)
--   * posts do corpus (is_anchor = FALSE): somente pt-BR
--   * posts-âncora (is_anchor = TRUE): existem apenas para ancorar a FK de
--     comentários cujo post pai não entrou no corpus pt-BR; podem ter qualquer
--     idioma (ou 'und' quando não há texto para detectar).
--   * nenhuma restrição de data; published_at pode ser qualquer data ou NULL
--
-- As tabelas de extensão são removidas por ON DELETE CASCADE.

-- Migração para bancos já existentes (a coluna também nasce no CREATE TABLE).
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_anchor BOOLEAN NOT NULL DEFAULT FALSE;

LOCK TABLE comments, posts IN SHARE ROW EXCLUSIVE MODE;

DELETE FROM comments
WHERE language IS DISTINCT FROM 'pt-BR';

-- Apenas posts do corpus precisam ser pt-BR. Posts-âncora são preservados:
-- remover o pai de um comentário válido recriaria o órfão que a recuperação
-- de pais resolve.
DELETE FROM posts
WHERE is_anchor = FALSE
  AND language IS DISTINCT FROM 'pt-BR';

ALTER TABLE posts
    ALTER COLUMN language SET NOT NULL,
    ALTER COLUMN published_at DROP NOT NULL,
    ALTER COLUMN is_anchor SET NOT NULL,
    ALTER COLUMN is_anchor SET DEFAULT FALSE,
    DROP CONSTRAINT IF EXISTS ck_posts_final_scope;

ALTER TABLE comments
    ALTER COLUMN language SET NOT NULL,
    ALTER COLUMN published_at DROP NOT NULL,
    DROP CONSTRAINT IF EXISTS ck_comments_final_scope;

ALTER TABLE posts ADD CONSTRAINT ck_posts_final_scope
    CHECK (is_anchor OR language = 'pt-BR');

ALTER TABLE comments ADD CONSTRAINT ck_comments_final_scope
    CHECK (language = 'pt-BR');

CREATE INDEX IF NOT EXISTS idx_comments_language ON comments (language);
CREATE INDEX IF NOT EXISTS idx_posts_is_anchor  ON posts (is_anchor);

SELECT 'posts' AS tabela, COUNT(*) AS total,
       COUNT(*) FILTER (WHERE published_at IS NULL) AS sem_data,
       MIN(published_at) AS mais_antigo,
       MAX(published_at) AS mais_recente
FROM posts
UNION ALL
SELECT 'comments', COUNT(*),
       COUNT(*) FILTER (WHERE published_at IS NULL),
       MIN(published_at), MAX(published_at)
FROM comments;
