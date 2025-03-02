"""Add initial specializations

Revision ID: b9504fabeae1
Revises: bacddca12f75
Create Date: 2025-03-01 14:40:30.659422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9504fabeae1'
down_revision: Union[str, None] = 'bacddca12f75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Wstawiamy dane do tabeli 'specializations'
    op.execute("""
    INSERT INTO specializations (id, title, short_description) VALUES
    ('aggression','Agresja','Problemy związane z agresywnymi zachowaniami, zarówno wobec ludzi, jak i innych zwierząt.'),
    ('anxiety','Lęk i niepokój','Zaburzenia lękowe, fobie, a także ogólny niepokój.'),
    ('leash_training','Trening smyczy','Eliminacja ciągnięcia i nauka właściwego zachowania na smyczy.'),
    ('socialization','Socjalizacja','Wsparcie w nauce interakcji ze zwierzętami i ludźmi.'),
    ('excessive_barking','Nadmierne szczekanie','Kontrola i redukcja nadmiernej wokalizacji.'),
    ('destructiveness','Zachowania destrukcyjne','Niszczenie przedmiotów, mebli czy otoczenia.'),
    ('separation_anxiety','Lęk separacyjny','Stres i destrukcyjne zachowania pod nieobecność właściciela.'),
    ('resource_guarding','Obrona zasobów','Agresywna reakcja związana z ochroną jedzenia czy zabawek.'),
    ('hyperactivity','Nadpobudliwość','Problemy z kontrolą energii i impulsywnością.'),
    ('obedience_training','Szkolenie posłuszeństwa','Trening dyscypliny i poprawy posłuszeństwa.'),
    ('clicker_training','Trening klikera','Metoda szkoleniowa oparta na pozytywnym wzmocnieniu z użyciem klikera.')
    """)

def downgrade():
    op.execute("""
    DELETE FROM specializations
     WHERE id IN (
       'aggression',
       'anxiety',
       'leash_training',
       'socialization',
       'excessive_barking',
       'destructiveness',
       'separation_anxiety',
       'resource_guarding',
       'hyperactivity',
       'obedience_training',
       'clicker_training'
     );
    """)