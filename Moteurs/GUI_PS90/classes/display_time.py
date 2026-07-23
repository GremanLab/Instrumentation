def display_time(seconds):
    """
    Display secondes in hours / minutes /secondes
    """
    days=seconds//(3600*24)
    hours=(seconds-days*(3600*24))//3600
    minutes=(seconds-days*(3600*24)-hours*3600)//60
    seconds_remaining=(seconds//1)%60

    if days !=0:
        print(f"{days} days, {hours} h, {minutes} min, {seconds_remaining} s")
    elif hours !=0:
        print(f"{hours} h, {minutes} min, {seconds_remaining} s")
    elif minutes !=0:
        print(f"{minutes} min, {seconds_remaining} s")
    else:
        print(f"{seconds_remaining} s")
    return days,hours,minutes,seconds_remaining

def display_time_str(seconds):
    """
    Return secondes in hours / minutes /secondes with string
    """
    days=seconds//(3600*24)
    hours=(seconds-days*(3600*24))//3600
    minutes=(seconds-days*(3600*24)-hours*3600)//60
    seconds_remaining=(seconds//1)%60

    if days !=0:
        return f"{days} days, {hours} h, {minutes} min, {seconds_remaining} s"
    elif hours !=0:
        return f"{hours} h, {minutes} min, {seconds_remaining} s"
    elif minutes !=0:
        return f"{minutes} min, {seconds_remaining} s"
    else:
        return f"{seconds_remaining} s"

