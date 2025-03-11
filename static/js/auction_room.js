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
          "/auction_house/api/v1/auction_room",
          null,
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
