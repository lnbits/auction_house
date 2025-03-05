window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {

      currencyOptions: [],
      auctionHouseForm: {
        show: false,
        data: auction_house,
      },
      auctionHouseTab: "overview",
    };
  },
  methods: {
    saveAuctionHouse: async function () {
      try {
        await LNbits.api.request(
          "PUT",
          "/bids/api/v1/auction_house",
          _.findWhere(this.g.user.wallets, {
            id: this.auctionHouseForm.data.wallet,
          }).adminkey,
          this.auctionHouseForm.data,
        );
        this.$q.notify({
          type: "positive",
          message: "Auction House updated!",
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
      this.auctionHouseForm.data.cost_extra.char_count_cost.push({
        bracket: 0,
        amount: 1,
      });
    },
    removeCharCountCost: function (index) {
      if (
        index < this.auctionHouseForm.data.cost_extra.char_count_cost.length
      ) {
        this.auctionHouseForm.data.cost_extra.char_count_cost.splice(index, 1);
      }
    },
    addRankCost: function () {
      this.auctionHouseForm.data.cost_extra.rank_cost.push({
        bracket: 0,
        amount: 1,
      });
    },
    removeRankCost: function (index) {
      if (index < this.auctionHouseForm.data.cost_extra.rank_cost.length) {
        this.auctionHouseForm.data.cost_extra.rank_cost.splice(index, 1);
      }
    },
    addPromotion: function () {
      this.auctionHouseForm.data.cost_extra.promotions.push({
        code: "",
        buyer_discount_percent: 0,
        referer_bonus_percent: 0,
      });
    },
    removePromotion: function (index) {
      if (index < this.auctionHouseForm.data.cost_extra.promotions.length) {
        this.auctionHouseForm.data.cost_extra.promotions.splice(index, 1);
      }
    },
  },
  created() {
    LNbits.api
      .request("GET", "/api/v1/currencies")
      .then((response) => {
        this.currencyOptions = ["sats", ...response.data];
      })
      .catch(LNbits.utils.notifyApiError);
  },
});
