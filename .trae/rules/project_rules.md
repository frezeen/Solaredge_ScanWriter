```markdown
# 🏗️ CLEAN CODE FRAMEWORK
**Version 2.0** | **Last Update:** Dynamic | **Priority:** MANDATORY

## 🔴 LIVELLO 1: PRINCIPI FONDAMENTALI (SEMPRE)

### 🎯 P1: SEARCH FIRST
Prima di scrivere: `search_codebase()` → `analyze_patterns()` → `reuse_or_extend()`

### 🎯 P2: SOLID PRINCIPLES
- **S**ingle Responsibility: Una classe, una responsabilità
- **O**pen/Closed: Estendi, non modificare
- **L**iskov: Sottotipi sostituibili senza rotture
- **I**nterface Segregation: Interfacce specifiche, non monolitiche
- **D**ependency Inversion: `__init__(self, logger: LoggerProtocol)`

### 🎯 P3: FAIL FAST & EXPLICIT
```python
if not (validated := self._validate(data)):
    raise ValidationError(f"Invalid: {data}")
return self._execute(validated)
```

## 🟡 LIVELLO 2: ARCHITETTURA & DESIGN

### 🏗️ A1: LAYERED ARCHITECTURE
```python
@dataclass(frozen=True)  # Domain Layer
class Invoice: amount: Decimal

class ProcessInvoiceUseCase:  # Application Layer
    def execute(self, invoice: Invoice) -> None

class DatabaseRepository:  # Infrastructure Layer
    async def save(self, entity: Entity) -> None
```

### 🏗️ A2: COMPOSITION > INHERITANCE
```python
# ✅ Prefer composition
class Service:
    def __init__(self, validator: Validator, processor: Processor):
        self._validator = validator
```

### 🏗️ A3: IMMUTABILITY BY DEFAULT
```python
@dataclass(frozen=True)
class Config:
    api_key: str
    timeout: int = 30
    
    def with_timeout(self, new_timeout: int) -> 'Config':
        return replace(self, timeout=new_timeout)
```

## 🟢 LIVELLO 3: IMPLEMENTAZIONE PYTHON

### 🐍 I1: MODERN PYTHON FEATURES
```python
def process(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    if (result := self._compute()) and result.valid:  # Walrus operator
        match result.status:  # Pattern matching 3.10+
            case "success": return result.data
            case "error": raise ProcessError(result.error)
    return {k: [v.upper() for v in vals] for k, vals in items.items()}  # Comprehensions
```

### 🐍 I2: ASYNC FIRST FOR I/O
```python
async def fetch_all(urls: list[str]) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        tasks = [self._fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### 🐍 I3: CONTEXT MANAGERS & DECORATORS
```python
@contextmanager
def timed_operation(name: str):
    start = time.perf_counter()
    try: yield
    finally: logger.info(f"{name}: {time.perf_counter() - start:.3f}s")

with timed_operation("database_query"):
    results = await db.query(sql)
```

## 🔵 LIVELLO 4: QUALITY ASSURANCE

### 🧪 Q1: TEST DRIVEN DEVELOPMENT
```python
def test_calculate_discount():  # Test first
    assert calculate_discount(100, "GOLD") == 80
    
def calculate_discount(amount: Decimal, tier: str) -> Decimal:  # Then implement
    return amount * DISCOUNT_RATES[tier]
```

### 📝 Q2: DOCUMENTATION AS CODE
```python
def process_transaction(amount: Decimal, currency: str = "EUR") -> TransactionResult:
    """Process a financial transaction.
    
    Args:
        amount: Transaction amount in decimal format
        currency: ISO 4217 currency code
        
    Returns:
        TransactionResult with status and transaction_id
        
    Raises:
        InsufficientFundsError: If balance too low
        
    Example:
        >>> result = process_transaction(Decimal("100.50"), "USD")
        >>> assert result.status == "completed"
    """
```

### 🔒 Q3: SECURITY BY DESIGN
```python
logger.info(f"User {user_id} authenticated")  # ✅ No sensitive data
# logger.info(f"Password: {password}")  # ❌ Never log secrets

def process_input(data: str) -> str:
    if not (clean := sanitize(data)):
        raise ValidationError("Invalid input")
    return clean
```

## ⚡ LIVELLO 5: PERFORMANCE & MONITORING

### 📊 M1: MEASURE THEN OPTIMIZE
```python
@profile
def expensive_operation(): pass  # Profile first

def process_large_file(path: Path) -> Iterator[dict]:  # Generators for large data
    with open(path) as f:
        for line in f:
            yield json.loads(line)
```

### 📈 M2: STRUCTURED LOGGING
```python
logger.info("api_request", extra={
    "user_id": user_id, "endpoint": endpoint,
    "duration_ms": duration, "status_code": response.status
})
```

## 🚀 EXECUTION PRIORITIES

1. **ALWAYS**: P1-P3 (Fundamental Principles)
2. **DESIGN**: A1-A3 (Architecture) 
3. **CODING**: I1-I3 (Implementation)
4. **COMMIT**: Q1-Q3 (Quality)
5. **DEPLOY**: M1-M2 (Monitoring)

## 📋 QUICK CHECKLIST
□ Searched existing code? | □ Single responsibility? | □ Error handling?
□ Type hints? | □ Tests written? | □ Documented? | □ Security validated?

## 🎯 GOLDEN RULES SUMMARY
- **SEARCH** before implementing
- **FAIL FAST** with clear errors  
- **COMPOSE** don't inherit
- **IMMUTABLE** by default
- **ASYNC** for I/O operations
- **TEST** before coding
- **DOCUMENT** with examples
- **VALIDATE** all inputs
- **MEASURE** before optimizing
- **LOG** structured data
```