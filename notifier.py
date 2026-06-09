from plyer import notification

def alert(title, msg):
    # Присылает уведомления
    notification.notify(
        title=title,
        message=msg,
        timeout=4
    )