import os
import psycopg2
import psycopg2.extras

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

def set_salary(phone_number, amount):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO salary (phone_number, amount) VALUES (%s, %s)",
            (phone_number, amount)
        )
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Sueldo registrado: ${amount} para esta semana"
    except Exception as e:
        return f"Error: {str(e)}"

def get_balance(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Sueldo de esta semana
        cur.execute(
            "SELECT SUM(amount) as total FROM salary WHERE phone_number = %s AND week_date >= date_trunc('week', CURRENT_DATE)",
            (phone_number,)
        )
        salary = cur.fetchone()
        salary_total = float(salary['total'] or 0)
        
        # Gastos de esta semana (Asume que expenses tabla existe)
        try:
            cur.execute(
                "SELECT SUM(amount) as total FROM expenses WHERE phone_number = %s AND expense_date >= date_trunc('week', CURRENT_DATE)",
                (phone_number,)
            )
            expenses = cur.fetchone()
            expenses_total = float(expenses['total'] or 0)
        except psycopg2.errors.UndefinedTable:
            conn.rollback() # recover from failed query
            expenses_total = 0.0

        # Gastos fijos
        cur.execute(
            "SELECT * FROM fixed_expenses WHERE phone_number = %s",
            (phone_number,)
        )
        fixed = cur.fetchall()
        cur.close()
        conn.close()
        
        available = salary_total - expenses_total
        pct_spent = (expenses_total / salary_total * 100) if salary_total > 0 else 0
        
        lines = [
            f"💰 *Balance semanal:*\n",
            f"📥 Sueldo: ${salary_total:.2f}",
            f"📤 Gastos: ${expenses_total:.2f}",
            f"✅ Disponible: ${available:.2f} ({100-pct_spent:.0f}% restante)"
        ]
        
        if fixed:
            lines.append("\n📋 *Gastos fijos pendientes:*")
            for f in fixed:
                lines.append(f"  • {f['name']}: ${f['amount']} ({f['frequency']})")
                
        if pct_spent >= 80:
            lines.append(f"\n⚠️ *Alerta:* Ya gastaste el {pct_spent:.0f}% de tu sueldo esta semana.")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error obteniendo balance: {str(e)}"

def add_fixed_expense(phone_number, name, amount, frequency):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO fixed_expenses (phone_number, name, amount, frequency) VALUES (%s, %s, %s, %s)",
            (phone_number, name, amount, frequency)
        )
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Gasto fijo agregado: {name} — ${amount} ({frequency})"
    except Exception as e:
        return f"Error: {str(e)}"

def get_stock_price(ticker):
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
        prices = [p for p in prices if p is not None]
        current = prices[-1]
        prev = prices[-2] if len(prices) > 1 else current
        change = ((current - prev) / prev) * 100
        emoji = "📈" if change >= 0 else "📉"
        return {"ticker": ticker, "price": round(current, 2), "change": round(change, 2), "prev": round(prev, 2), "emoji": emoji}
    except:
        return None

def get_week_performance(ticker):
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=7d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
        prices = [p for p in prices if p is not None]
        week_start = prices[0]
        week_end = prices[-1]
        change_pct = ((week_end - week_start) / week_start) * 100
        return {"ticker": ticker, "week_start": round(week_start, 2), "week_end": round(week_end, 2), "change_pct": round(change_pct, 2)}
    except:
        return None

def add_position(phone_number, ticker, shares, price):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolio WHERE phone_number = %s AND ticker = %s", (phone_number, ticker.upper()))
        existing = cur.fetchone()
        if existing:
            total_shares = float(existing['shares']) + shares
            total_cost = (float(existing['shares']) * float(existing['avg_price'])) + (shares * price)
            new_avg = total_cost / total_shares
            cur.execute("UPDATE portfolio SET shares = %s, avg_price = %s WHERE phone_number = %s AND ticker = %s", (total_shares, new_avg, phone_number, ticker.upper()))
        else:
            cur.execute("INSERT INTO portfolio (phone_number, ticker, shares, avg_price) VALUES (%s, %s, %s, %s)", (phone_number, ticker.upper(), shares, price))
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Compra registrada: {shares} acciones de {ticker.upper()} a ${price}"
    except Exception as e:
        return f"Error: {str(e)}"

def remove_position(phone_number, ticker, shares, price):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolio WHERE phone_number = %s AND ticker = %s", (phone_number, ticker.upper()))
        existing = cur.fetchone()
        if not existing:
            return f"No tienes acciones de {ticker.upper()} en tu portafolio."
        new_shares = float(existing['shares']) - shares
        if new_shares <= 0:
            cur.execute("DELETE FROM portfolio WHERE phone_number = %s AND ticker = %s", (phone_number, ticker.upper()))
        else:
            cur.execute("UPDATE portfolio SET shares = %s WHERE phone_number = %s AND ticker = %s", (new_shares, phone_number, ticker.upper()))
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Venta registrada: {shares} acciones de {ticker.upper()} a ${price}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_portfolio_summary(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolio WHERE phone_number = %s", (phone_number,))
        positions = cur.fetchall()
        cur.close()
        conn.close()
        if not positions:
            return "No tienes acciones registradas."
        
        lines = ["📊 *Portafolio hoy:*\n"]
        total_day_gain = 0
        
        for pos in positions:
            stock = get_stock_price(pos['ticker'])
            if stock:
                day_gain = stock['change'] / 100 * stock['price'] * float(pos['shares'])
                total_day_gain += day_gain
                emoji = "📈" if day_gain >= 0 else "📉"
                lines.append(f"{emoji} {pos['ticker']}: {stock['change']:+.2f}% (${day_gain:+.2f} hoy)")
        
        total_emoji = "📈" if total_day_gain >= 0 else "📉"
        lines.append(f"\n{total_emoji} *Total del día: ${total_day_gain:+.2f}*")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def add_expense(phone_number, amount, category, description=""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO expenses (phone_number, amount, category, description) VALUES (%s, %s, %s, %s)", (phone_number, amount, category, description))
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Gasto registrado: ${amount} en {category}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_expenses_summary(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT category, SUM(amount) as total FROM expenses WHERE phone_number = %s AND expense_date = CURRENT_DATE GROUP BY category ORDER BY total DESC", (phone_number,))
        expenses = cur.fetchall()
        cur.close()
        conn.close()
        if not expenses:
            return "No has registrado gastos hoy."
        lines = ["💸 *Gastos de hoy:*\n"]
        total = 0
        for e in expenses:
            lines.append(f"• {e['category']}: ${e['total']:.2f}")
            total += float(e['total'])
        lines.append(f"\n💰 *Total hoy:* ${total:.2f}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def get_weekly_report(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolio WHERE phone_number = %s", (phone_number,))
        positions = cur.fetchall()
        cur.close()
        conn.close()
        if not positions:
            return "No tienes acciones en tu portafolio."
        winners = []
        losers = []
        for pos in positions:
            perf = get_week_performance(pos['ticker'])
            if perf:
                shares = float(pos['shares'])
                gain = (perf['week_end'] - perf['week_start']) * shares
                perf['gain'] = gain
                perf['shares'] = shares
                if gain >= 0:
                    winners.append(perf)
                else:
                    losers.append(perf)
        winners.sort(key=lambda x: x['change_pct'], reverse=True)
        losers.sort(key=lambda x: x['change_pct'])
        lines = ["📊 *Reporte semanal de acciones:*\n"]
        if winners:
            lines.append("🟢 *Ganadores:*")
            for w in winners:
                lines.append(f"  📈 {w['ticker']}: +{w['change_pct']:.2f}% (${w['gain']:+.2f})")
        if losers:
            lines.append("\n🔴 *Perdedores:*")
            for l in losers:
                lines.append(f"  📉 {l['ticker']}: {l['change_pct']:.2f}% (${l['gain']:+.2f})")
        total_gain = sum(p['gain'] for p in winners + losers)
        lines.append(f"\n💰 *Resultado neto:* ${total_gain:+.2f}")
        if total_gain < 0:
            lines.append("\n💡 *Recomendación:* Semana difícil. Mantén posiciones a largo plazo.")
        else:
            lines.append("\n💡 *Recomendación:* ¡Buena semana! Revisa si alguna posición está sobrevaluada.")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
