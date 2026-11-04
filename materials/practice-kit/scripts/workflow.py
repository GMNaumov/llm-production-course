"""Человеческий preview/confirm локального синтетического изменения.
Не вызывается model_server и не является инструментом модели.
"""

from tools import confirm, connect, preview

if __name__ == "__main__":
    db = connect()
    try:
        actor = "engineer-a"  # Учебная серверная личность; не ответ модели.
        plan = preview(db, actor, "A", "TRN-0001", 12)
        effect = plan["effect"]
        print(
            f"ТЕСТОВЫЙ заказ {effect['order_id']}, версия {effect['version']}, шт.: {effect['old']} -> {effect['new']}"
        )
        print(
            "Срок preview 300 секунд; последствие — одно изменение количества в локальной SQLite."
        )
        response = input(
            "Для явного подтверждения этого изменения введите ПОДТВЕРЖДАЮ; иначе отказ: "
        )
        if response == "ПОДТВЕРЖДАЮ":
            result = confirm(db, actor, "A", plan["confirmation_id"], True)
            print("Применено в тесте:", result)
        else:
            print("Отказ пользователя. Изменение не применено.")
    finally:
        db.close()
