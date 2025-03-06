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
  },
  created() {
    LNbits.api
      .request("GET", "/api/v1/currencies")
      .then((response) => {
        this.currencyOptions = ["sat", ...response.data];
      })
      .catch(LNbits.utils.notifyApiError);
  },
});
