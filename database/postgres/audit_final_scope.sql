-- A única violação de escopo possível é idioma diferente de pt-BR nos
-- comentários e nos posts do corpus. Posts-âncora (is_anchor) são isentos:
-- existem só para ancorar a FK dos comentários ao post pai.
SELECT 'comments' AS tabela,
       COUNT(*) FILTER (WHERE language IS DISTINCT FROM 'pt-BR') AS violacoes,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE published_at IS NULL) AS sem_data,
       MIN(published_at) AS mais_antigo,
       MAX(published_at) AS mais_recente
FROM comments
UNION ALL
SELECT 'posts (corpus)',
       COUNT(*) FILTER (WHERE NOT is_anchor AND language IS DISTINCT FROM 'pt-BR'),
       COUNT(*) FILTER (WHERE NOT is_anchor),
       COUNT(*) FILTER (WHERE NOT is_anchor AND published_at IS NULL),
       MIN(published_at) FILTER (WHERE NOT is_anchor),
       MAX(published_at) FILTER (WHERE NOT is_anchor)
FROM posts
UNION ALL
SELECT 'posts (âncora)',
       NULL,
       COUNT(*) FILTER (WHERE is_anchor),
       NULL, NULL, NULL
FROM posts;

SELECT platform, source_system, COUNT(*) AS total
FROM posts
GROUP BY platform, source_system
ORDER BY platform, source_system;

SELECT platform, source_system, COUNT(*) AS total
FROM comments
GROUP BY platform, source_system
ORDER BY platform, source_system;
