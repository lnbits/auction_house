window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      currencyOptions: [],
      auctionRoomForm: {
        show: false,
        data: auction_room,
      },
      auctionRoomTab: "overview",
    };
  },
  methods: {
    saveAuctionRoom: async function () {
      try {
        await LNbits.api.request(
          "PUT",
          "/bids/api/v1/auction_room",
          _.findWhere(this.g.user.wallets, {
            id: this.auctionRoomForm.data.wallet,
          }).adminkey,
          this.auctionRoomForm.data,
        );
        this.$q.notify({
          type: "positive",
          message: "Auction Room updated!",
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
