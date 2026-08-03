-- A única violação de escopo possível é idioma diferente de pt-BR.
SELECT 'posts' AS tabela,
       COUNT(*) FILTER (WHERE language IS DISTINCT FROM 'pt-BR') AS violacoes,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE published_at IS NULL) AS sem_data,
       MIN(published_at) AS mais_antigo,
       MAX(published_at) AS mais_recente
FROM posts
UNION ALL
SELECT 'comments',
       COUNT(*) FILTER (WHERE language IS DISTINCT FROM 'pt-BR'),
       COUNT(*),
       COUNT(*) FILTER (WHERE published_at IS NULL),
       MIN(published_at), MAX(published_at)
FROM comments;

SELECT platform, source_system, COUNT(*) AS total
FROM posts
GROUP BY platform, source_system
ORDER BY platform, source_system;

SELECT platform, source_system, COUNT(*) AS total
FROM comments
GROUP BY platform, source_system
ORDER BY platform, source_system;
