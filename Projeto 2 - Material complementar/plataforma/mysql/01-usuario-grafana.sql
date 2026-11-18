-- Usuário somente leitura do Grafana
CREATE USER IF NOT EXISTS 'grafana'@'%' IDENTIFIED BY 'grafana2026';
GRANT SELECT ON `fei`.* TO 'grafana'@'%';
FLUSH PRIVILEGES;
