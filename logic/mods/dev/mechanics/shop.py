from logic.mechanics.common import *
from logic.mechanics import import_mod_module as import_
ITEM = import_('items.items').ITEM


class Shop:
    @classmethod
    def find_iid(cls, iid):
        for item in ITEM:
            if item.value == round(iid):
                return item
        return None

    @classmethod
    def do_buy_shop(cls, api, uid):
        iid = round(api.get_status(uid, STATUS.SHOP))
        item = cls.find_iid(iid)
        if item is None:
            return FAIL_RESULT.MISSING_TARGET

        result = cls._do_buy(api, uid, item)

        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'shop'})
        logger.debug(f'{api.units[uid].name} bought item: {item.name} ({item.value})')
        return result

    @classmethod
    def _do_buy(cls, api, uid, item):
        cls.apply_cost(api, uid, item)
        cls.apply_stats(api, uid, item)

    @classmethod
    def apply_cost(cls, api, uid, item):
        api.set_stats(uid, STAT.GOLD, -ITEM_STATS[item]['cost'], additive=True)

    @classmethod
    def apply_stats(cls, api, uid, item):
        for stat, values in ITEM_STATS[item]['stats']:
            for value_name, value in values.items():
                api.set_stats(uid, stat, value, value_name=value_name, additive=True)
