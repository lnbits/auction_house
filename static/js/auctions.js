window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      addresses: [],
      addressesTable: {
        columns: [
          {
            name: "name",
            align: "left",
            label: "Name",
            field: "name",
            sortable: true,
          },
          {
            name: "description",
            align: "left",
            label: "Description",
            field: "description",
            sortable: false,
          },
          {
            name: "starting_price",
            align: "left",
            label: "Sarting Price",
            field: "starting_price",
            sortable: true,
          },
          {
            name: "current_price",
            align: "left",
            label: "Current Price",
            field: "current_price",
            sortable: true,
          },
          {
            name: "created_at",
            align: "left",
            label: "Created At",
            field: "created_at",
            sortable: true,
          },
          {
            name: "expires_at",
            align: "left",
            label: "Expires At",
            field: "expires_at",
            sortable: true,
          },

          { name: "id", align: "left", label: "ID", field: "id" },
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10,
        },
      },

      currencyOptions: [],
      auctionHouseForm: {
        show: false,
        data: auction_house,
      },
      auctionHouseTab: "overview",
    };
  },
  methods: {
    getAddresses: function (props) {
      var self = this;
      if (props) {
        self.addressesTable.pagination = props.pagination;
      }
      let pagination = self.addressesTable.pagination;
      const query = {
        all_wallets: true,
        limit: pagination.rowsPerPage,
        offset: (pagination.page - 1) * pagination.rowsPerPage ?? 0,
        sortby: pagination.sortBy || "time",
        direction: pagination.descending ? "desc" : "asc",
      };
      const params = new URLSearchParams(query);

      LNbits.api
        .request(
          "GET",
          `/bids/api/v1/addresses/paginated?${params}`,
          this.g.user.wallets[0].inkey,
        )
        .then(function (response) {
          const { data, total } = response.data;
          self.addressesTable.pagination.rowsNumber = total;
          self.addresses = data.map(function (obj) {
            return mapAuctionHouse(obj);
          });
        });
    },
  },
  created() {},
});
