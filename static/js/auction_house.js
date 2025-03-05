window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      auction_houseRankingBraketOptions: [
        200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
        1000000,
      ],
      currencyOptions: [],
      auction_houseForm: {
        show: false,
        data: auction_house,
      },
      auction_houseTab: "charCount",
    };
  },
  methods: {
    resetFormDialog: function () {
      this.auction_houseForm.show = false;
      this.auction_houseTab = "charCount";
    },
    saveAuctionHouse: async function () {
      try {
        await LNbits.api.request(
          "PUT",
          "/bids/api/v1/auction_house",
          _.findWhere(this.g.user.wallets, { id: this.auction_houseForm.data.wallet })
            .adminkey,
          this.auction_houseForm.data,
        );
        this.$q.notify({
          type: "positive",
          message: "AuctionHouse updated!",
        });
      } catch (error) {
        this.$q.notify({
          type: "negative",
          message: "Failed to update!",
        });
        LNbits.utils.notifyApiError(error);
      }
    },
    addCharCountCost: function () {
      this.auction_houseForm.data.cost_extra.char_count_cost.push({
        bracket: 0,
        amount: 1,
      });
    },
    removeCharCountCost: function (index) {
      if (index < this.auction_houseForm.data.cost_extra.char_count_cost.length) {
        this.auction_houseForm.data.cost_extra.char_count_cost.splice(index, 1);
      }
    },
    addRankCost: function () {
      this.auction_houseForm.data.cost_extra.rank_cost.push({
        bracket: 0,
        amount: 1,
      });
    },
    removeRankCost: function (index) {
      if (index < this.auction_houseForm.data.cost_extra.rank_cost.length) {
        this.auction_houseForm.data.cost_extra.rank_cost.splice(index, 1);
      }
    },
    addPromotion: function () {
      this.auction_houseForm.data.cost_extra.promotions.push({
        code: "",
        buyer_discount_percent: 0,
        referer_bonus_percent: 0,
      });
    },
    removePromotion: function (index) {
      if (index < this.auction_houseForm.data.cost_extra.promotions.length) {
        this.auction_houseForm.data.cost_extra.promotions.splice(index, 1);
      }
    },
  },
  created() {
    this.resetFormDialog();
  },
});
