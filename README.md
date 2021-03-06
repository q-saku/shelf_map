shelf_map
=========

Описание
--------
Данный инструмент предназначен для работы с полками под управлением HBA контроллеров.

С приходом HBA контроллеров вместо RAID появилась проблема с определением 
физического местоположения дисков относительно наименования дисков в системе. 
Особенно остро эта проблема встала в ОС FreeBSD, где, как правило, нет утилит для работы с HBA.
Это внесло свои ограничения в администрировании связки FreeBSD + HBA + полка.
Данное решение использует утилиту sg3_utils для осуществления возможности работы с такой связкой.

Синтаксис
--------
    shelf_map.py [options] [drive]

Требования
--------
1. Python 2.6 и выше
2. Пакет sysutils/sg3_utils(sg3-utils)
3. Права пользователя root

Особенности
-------
В данной реализации подразумевается, что одна полка подключена к одному экспандеру.
В противном случае информация о местоположении может не соответствовать реальной.
Возможность управлять подсветкой дисков остается.

Инструмент писался в первую очередь для работы с FreeBSD. Работа с Linux была реализована по запросу 
и не была протестирована на большом количестве серверов.

Возможности
-------
1. Работает с операционными системами FreeBSD и Linux
2. Умеет подсвечивать указанный диск
3. Умеет убирать подсветку указанного диска
4. Умеет отслеживать пустые слоты
5. Умеет печатать только подсвеченные или только пустые слоты
6. Запущенный без опций или с опцией -p, выводит табличку с информацией о дисках и полках
7. Можно использовать в качестве модуля python

Пример вывода
-------
    DRIVE: da4       SHELF: 1    SLOT: 0    LOCATE: Off    SERIAL: Z1Z0EKFL
    DRIVE: da5       SHELF: 1    SLOT: 1    LOCATE: Off    SERIAL: Z1Y03CY9
    DRIVE: da14      SHELF: 1    SLOT: 2    LOCATE: Off    SERIAL: Z1Z0EPF8
    DRIVE: da12      SHELF: 1    SLOT: 3    LOCATE: Off    SERIAL: Z1Z0EYV4
    DRIVE: da8       SHELF: 1    SLOT: 4    LOCATE: Off    SERIAL: Z1Z0E185
