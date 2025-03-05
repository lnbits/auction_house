window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      addresses: [],
      addressesTable: {
        columns: [
          { name: "id", align: "left", label: "ID", field: "id" },
          {
            name: "active",
            align: "left",
            label: "Active",
            field: "active",
            sortable: true,
          },
          {
            name: "local_part",
            align: "left",
            label: "Address",
            field: "local_part",
            sortable: true,
          },
          {
            name: "pubkey",
            align: "left",
            label: "Pubkey",
            field: "pubkey",
            sortable: true,
          },
          {
            name: "reimburse_amount",
            align: "left",
            label: "Reimburse",
            field: "reimburse_amount",
            sortable: true,
          },
          {
            name: "time",
            align: "left",
            label: "Created At",
            field: "time",
            sortable: true,
          },
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
