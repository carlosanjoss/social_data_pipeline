-- Escopo obrigatório do banco final:
--   * somente português brasileiro (código canônico pt-BR)
--   * nenhuma restrição de data; published_at pode ser qualquer data ou NULL
--
-- As tabelas de extensão são removidas por ON DELETE CASCADE.

LOCK TABLE comments, posts IN SHARE ROW EXCLUSIVE MODE;

DELETE FROM comments
WHERE language IS DISTINCT FROM 'pt-BR';

-- Um comentário válido pode apontar para um post descartado por idioma.
UPDATE comments c
SET post_pk = NULL
FROM posts p
WHERE c.post_pk = p.id
  AND p.language IS DISTINCT FROM 'pt-BR';

DELETE FROM posts
WHERE language IS DISTINCT FROM 'pt-BR';

ALTER TABLE posts
    ALTER COLUMN language SET NOT NULL,
    ALTER COLUMN published_at DROP NOT NULL,
    DROP CONSTRAINT IF EXISTS ck_posts_final_scope;

ALTER TABLE comments
    ALTER COLUMN language SET NOT NULL,
    ALTER COLUMN published_at DROP NOT NULL,
    DROP CONSTRAINT IF EXISTS ck_comments_final_scope;

ALTER TABLE posts ADD CONSTRAINT ck_posts_final_scope
    CHECK (language = 'pt-BR');

ALTER TABLE comments ADD CONSTRAINT ck_comments_final_scope
    CHECK (language = 'pt-BR');

CREATE INDEX IF NOT EXISTS idx_comments_language ON comments (language);

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
