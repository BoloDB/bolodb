"""Creates TechStore sample database on first run."""
import sqlite3
import os
from pathlib import Path

def ensure_sample_db():
    path = Path(os.path.expanduser("~")) / ".bolodb" / "sample_techstore.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return f"sqlite:///{path.as_posix()}"
    c = sqlite3.connect(str(path))
    c.executescript("""
    CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,email TEXT,segment TEXT,country TEXT,created_at TEXT);
    CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT,category TEXT,price REAL,stock INTEGER);
    CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER,status TEXT,total_amount REAL,created_at TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id));
    CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,product_id INTEGER,quantity INTEGER,unit_price REAL,
        FOREIGN KEY(order_id) REFERENCES orders(id),FOREIGN KEY(product_id) REFERENCES products(id));
    CREATE TABLE payments(id INTEGER PRIMARY KEY,order_id INTEGER,method TEXT,amount REAL,paid_at TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id));

    INSERT INTO customers VALUES
      (1,'Ananya Rao','ananya@mail.com','vip','India','2025-11-02'),
      (2,'Marcus Hale','marcus@mail.com','business','USA','2026-01-15'),
      (3,'Priya Menon','priya@mail.com','vip','India','2025-08-20'),
      (4,'Devin Cole','devin@mail.com','consumer','UK','2026-03-10'),
      (5,'Sofia Lund','sofia@mail.com','business','Sweden','2025-12-01'),
      (6,'Tom Becker','tom@mail.com','consumer','Germany','2026-02-22');

    INSERT INTO products VALUES
      (1,'Aurora 14" Laptop','laptops',1299.00,3),
      (2,'Zephyr Phone X','phones',699.00,14),
      (3,'NovaBuds Pro','audio',149.00,6),
      (4,'PixelView 27"','monitors',449.00,8),
      (5,'Glide Wireless Mouse','accessories',49.00,11),
      (6,'TypeMaster Keyboard','peripherals',129.00,22),
      (7,'PowerHub USB-C','accessories',39.00,85),
      (8,'SoundBar S1','audio',199.00,31);

    INSERT INTO orders VALUES
      (101,1,'completed',7498.00,'2026-06-02'),
      (102,2,'completed',6210.00,'2026-06-01'),
      (103,3,'completed',5880.00,'2026-05-28'),
      (104,4,'pending',4999.00,'2026-06-03'),
      (105,5,'completed',5120.00,'2026-06-04'),
      (106,6,'completed',798.00,'2026-05-20'),
      (107,1,'completed',3499.00,'2026-04-12'),
      (108,2,'cancelled',1299.00,'2026-03-01'),
      (109,3,'completed',449.00,'2026-06-05'),
      (110,4,'completed',149.00,'2026-05-30');

    INSERT INTO order_items VALUES
      (1,101,1,1,1299),(2,101,2,1,699),(3,102,6,1,129),(4,103,3,2,149),
      (5,104,1,1,1299),(6,105,4,1,449),(7,106,5,2,49),(8,107,8,1,199),
      (9,108,6,1,129),(10,109,4,1,449),(11,110,3,1,149);

    INSERT INTO payments VALUES
      (1,101,'card',7498.00,'2026-06-02'),
      (2,102,'paypal',6210.00,'2026-06-01'),
      (3,103,'card',5880.00,'2026-05-28'),
      (5,105,'bank',5120.00,'2026-06-04'),
      (6,106,'card',798.00,'2026-05-20');
    """)
    c.commit()
    c.close()
    print(f"Sample database created: {path}")
    return f"sqlite:///{path.as_posix()}"

if __name__ == "__main__":
    print(ensure_sample_db())
