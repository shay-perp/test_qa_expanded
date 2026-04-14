from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Circutor_Ammeter import CircutorAmmeter
from src.utils.constants import KEY_GREENLEE, KEY_ENTES, KEY_CIRCUTOR

AMMETER_REGISTRY = {
    KEY_GREENLEE: GreenleeAmmeter,
    KEY_ENTES:    EntesAmmeter,
    KEY_CIRCUTOR: CircutorAmmeter,
}

