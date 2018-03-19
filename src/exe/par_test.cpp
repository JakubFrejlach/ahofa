/// @author Jakub Semric
/// 2018

#include <iostream>
#include <ostream>
#include <sstream>
#include <exception>
#include <vector>
#include <map>
#include <stdexcept>
#include <ctype.h>
#include <getopt.h>

#include "nfa.hpp"
#include "pcap_reader.hpp"
#include "reduction.hpp"
#include "nfa_error.hpp"

using namespace reduction;
using namespace std;

const unsigned NW = 2;

int main()
{
    FastNfa target;
    target.read_from_file("min-snort/backdoor.rules.fa");

    string train_aggr = "pcaps/geant.pcap";
    vector<string> test_aggr{
        "pcaps/geant2.pcap2","pcaps/week2.pcap","pcaps/meter4-1.pcap8"};
    float pct = 0.16;

    for (int iter = 0; iter < 22; iter += 1)
    
    {
        FastNfa reduced = target;
        // 4 thresholds
        for (float threshold = 0.9; threshold < 1; threshold += 0.005)
        {
            // reduce
            FastNfa reduced = target;
            reduce(reduced, train_aggr, pct, threshold, iter);

            // compute error
            NfaError err{target, reduced, test_aggr, NW};
            err.start();

            // accumulate results
            ErrorStats aggr(target.state_count(), reduced.state_count());
            for (auto i : err.get_result())
            {
                aggr.aggregate(i.second);
            }

            size_t wrong_acceptances = aggr.accepted_reduced -
                aggr.accepted_target;
            float pe = wrong_acceptances * 1.0 / aggr.total;
            float ce = aggr.wrongly_classified * 1.0 / aggr.total;
            float cls_ratio = aggr.correctly_classified * 1.0 /
                (aggr.correctly_classified + aggr.wrongly_classified);

            cout << iter << " " << threshold << " " << pe << " " << ce
                << " " << cls_ratio << endl;

            // do not compute with different threshold for no iteration (prune)
            if (iter == 0)
            {
                break;
            }
        }
    }

    return 0;    
}