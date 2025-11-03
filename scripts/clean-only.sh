#!/bin/bash
# SolarEdge ScanWriter - Clean Only Script
# Solo pulizia sistema senza test

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧹 SolarEdge ScanWriter - Clean Only${NC}"
echo -e "${BLUE}===================================${NC}"

# Conferma
read -p "$(echo -e ${YELLOW}⚠️ Questo cancellerà TUTTO Docker. Continuare?${NC}) [y/N]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Operazione annullata${NC}"
    exit 0
fi

echo -e "${YELLOW}🐳 Pulizia Docker completa...${NC}"

# Stop e rimuovi tutto
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true
docker rmi $(docker images -q) 2>/dev/null || true
docker volume rm $(docker volume ls -q) 2>/dev/null || true
docker network rm $(docker network ls -q --filter type=custom) 2>/dev/null || true
docker system prune -a -f --volumes

echo -e "${YELLOW}📁 Rimozione progetto...${NC}"
cd /root
rm -rf Solaredge_ScanWriter

echo -e "${GREEN}✅ Pulizia completata!${NC}"
echo -e "${BLUE}Sistema pronto per nuovo test${NC}"

# Verifica pulizia
echo -e "${BLUE}📊 Verifica pulizia:${NC}"
echo "Container: $(docker ps -a | wc -l) (dovrebbe essere 1 - solo header)"
echo "Immagini: $(docker images | wc -l) (dovrebbe essere 1 - solo header)"
echo "Volumi: $(docker volume ls | wc -l) (dovrebbe essere 1 - solo header)"