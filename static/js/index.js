window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      auctionRooms: [],
      biddingType: [
        { value: "auction", label: "Auction" },
        { value: "fixed_price", label: "Fixed Price" },
      ],

      currencyOptions: [],
      auctionRoomsTable: {
        columns: [
          {
            name: "created_at",
            align: "left",
            label: "Created At",
            field: "created_at",
            format: (val) => LNbits.utils.formatDateString(val),
          },

          {
            name: "name",
            align: "left",
            label: "Name",
            field: "name",
          },
          {
            name: "currency",
            align: "left",
            label: "Currency",
            field: "currency",
          },
          { name: "type", align: "left", label: "Type", field: "type" },
          { name: "days", align: "left", label: "Days", field: "days" },
          {
            name: "room_percentage",
            align: "left",
            label: "Room %",
            field: "room_percentage",
          },
          {
            name: "min_bid_up_percentage",
            align: "left",
            label: "Min Bid %",
            field: "min_bid_up_percentage",
          },
          { name: "id", align: "left", label: "Room Id", field: "id" },
        ],
        pagination: {
          rowsPerPage: 10,
        },
      },

      formDialog: {
        show: false,
        data: {},
      },
      auctionRoomTab: null,

      qrCodeDialog: {
        show: false,
        data: {},
      },
    };
  },
  methods: {
    resetFormDialog: function () {
      this.formDialog.show = false;
      this.auctionRoomTab = "webhooks";
      this.formDialog.data = {
        name: "",
        description: "",
        wallet: "",
        currency: "sat",
        type: null,
      };
    },
    showFormDialog: function () {
      this.resetFormDialog();
      this.formDialog.show = true;
    },

    getAuctionRooms: async function () {
      try {
        const { data } = await LNbits.api.request(
          "GET",
          "/auction_house/api/v1/auction_rooms",
        );

        this.auctionRooms = data;
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },

    saveAuctionRoom: async function () {
      try {
        const { data } = await LNbits.api.request(
          "POST",
          "/auction_house/api/v1/auction_room",
          null,
          this.formDialog.data,
        );

        this.auctionRooms.push(data);
        this.resetFormDialog();
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },

    deleteAuctionRoom: function (auction_room_id) {
      var self = this;
      var auction_room = _.findWhere(this.auctionRooms, {
        id: auction_room_id,
      });

      LNbits.utils
        .confirmDialog("Are you sure you want to delete this auction room?")
        .onOk(function () {
          LNbits.api
            .request(
              "DELETE",
              "/auction_house/api/v1/auction_room/" + auction_room_id,
              _.findWhere(self.g.user.wallets, { id: auction_room.wallet })
                .adminkey,
            )
            .then(function (response) {
              self.auctionRooms = self.auctionRooms.filter(
                (d) => d.id !== auction_room_id,
              );
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error);
            });
        });
    },
    exportCSV: function () {
      LNbits.utils.exportCSV(this.auctionRoomsTable.columns, this.auctionRooms);
    },
  },
  created() {
    this.resetFormDialog();

    this.getAuctionRooms();

    LNbits.api
      .request("GET", "/api/v1/currencies")
      .then((response) => {
        this.currencyOptions = ["sat", ...response.data];
      })
      .catch(LNbits.utils.notifyApiError);
  },
  computed: {
    auctionRoomOptions: function () {
      return this.auctionRooms.map((el) => {
        return {
          label: el.auction_room,
          value: el.id,
        };
      });
    },
  },
});
